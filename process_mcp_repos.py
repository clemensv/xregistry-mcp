import json
import os
import subprocess
import tempfile
import shutil
import logging
import argparse
import sys
from azure.ai.inference import ChatCompletionsClient
from azure.identity import DefaultAzureCredential
from azure.core.exceptions import ResourceNotFoundError, HttpResponseError
from azure.core.credentials import AzureKeyCredential

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Configuration ---
SEED_FILE = 'seed.json'
OUTPUT_DIR_BASE = os.path.join('registry','mcpproviders')

# Defaults for minimal provisioning; using naming consistent with xregistry conventions
DEFAULT_RESOURCE_GROUP_NAME = "xregistry-mcp-rg"
DEFAULT_AZURE_LOCATION = "eastus"
DEFAULT_AI_PROJECT_NAME = "xregistry-mcp-project"
# We deploy a cost-effective, high-performance model; gpt-35-turbo balances quality and speed for code analysis
DEFAULT_AOAI_DEPLOYMENT_NAME = "gpt-4.1-mini"
DEFAULT_AOAI_MODEL_NAME = "gpt-4.1-mini"

# Assumes Azure OpenAI environment variables are set:
# AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY or relevant DefaultAzureCredential vars
# AZURE_OPENAI_DEPLOYMENT_NAME should be set to your chosen model deployment (e.g., gpt-4)

# Azure OpenAI Client Setup removed; using ChatCompletionsClient via get_chat_client

def get_chat_client(rg_name: str) -> ChatCompletionsClient:
    # Determine endpoint: env var overrides default naming
    openai_name = f"{rg_name}-openai"
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", f"https://{openai_name}.openai.azure.com")
    credential = DefaultAzureCredential()
    key = os.getenv("AZURE_OPENAI_API_KEY")
    logging.info(f"Initializing ChatCompletionsClient with endpoint: {endpoint}")
    return ChatCompletionsClient(endpoint=endpoint, credential=AzureKeyCredential(key))

def provision_resources(subscription_id: str, rg_name: str, location: str, project_name: str, deployment_name: str, model_name: str):
    # Create resource group
    logging.info(f"Ensuring resource group '{rg_name}' in '{location}'")
    subprocess.run(['az', 'group', 'create', '--name', rg_name, '--location', location], check=True, shell=True)
    # Create Azure OpenAI resource
    openai_name = f"{rg_name}-openai"
    logging.info(f"Creating Azure OpenAI account '{openai_name}'")
    subprocess.run([
        'az', 'cognitiveservices', 'account', 'create',
        '--name', openai_name,
        '--resource-group', rg_name,
        '--kind', 'OpenAI',
        '--sku', 'S0',
        '--location', location,
        '--yes'
    ], check=True, shell=True)
    # ensure OpenAI CLI extension
    subprocess.run(['az', 'extension', 'add', '--name', 'openai'], check=False, shell=True)
    # deploy the model into the Cognitiveservices resource using deployment create command
    logging.info(f"Deploying model '{model_name}' as deployment '{deployment_name}' on {openai_name}")
    subprocess.run([
        'az', 'cognitiveservices', 'account', 'deployment', 'create',
        '--name', openai_name,
        '--resource-group', rg_name,
        '--deployment-name', deployment_name,
        '--model-name', model_name,
        '--model-version', "1",
        '--model-format', "OpenAI",
        '--sku-capacity', "1",
        '--sku-name', "Standard"
    ], check=True, shell=True)
    logging.info("Provisioning complete")

def deprovision_resources(subscription_id: str, rg_name: str, project_name: str, deployment_name: str, delete_resource_group: bool = False):
    # Remove Azure OpenAI account and optionally resource group
    openai_name = f"{rg_name}-openai"
    logging.info(f"Deleting Azure OpenAI account '{openai_name}' if exists")
    subprocess.run(['az', 'cognitiveservices', 'account', 'delete', '--name', openai_name, '--resource-group', rg_name, '--yes'], check=False, shell=True)
    if delete_resource_group:
        logging.info(f"Deleting resource group '{rg_name}' and all contents")
        subprocess.run(['az', 'group', 'delete', '--name', rg_name, '--yes', '--no-wait'], check=False, shell=True)
    logging.info("Deprovisioning complete")

def get_repo_metadata_with_llm(repo_path: str, chat_client: ChatCompletionsClient ) -> dict | None:
    """
    Analyzes the cloned repository using an LLM to determine if it's an MCP server
    and extracts metadata based on the xregistry schema.

    Args:
        repo_path: path to local clone
        subscription_id, rg_name, project_name, deployment_name: Azure AI config

    Returns:
        server metadata dict or None
    """
    logging.info(f"Analyzing repository at: {repo_path}")
    readme_content = ""
    readme_path = os.path.join(repo_path, 'README.md')
    if os.path.exists(readme_path):
        try:
            with open(readme_path, 'r', encoding='utf-8', errors='ignore') as f:
                readme_content = f.read()
            logging.info("Read README.md")
        except Exception as e:
            logging.warning(f"Could not read README.md: {e}")

    source_code_snippets = []
    
    # Walk through the repository folder to search for .py, .js, and .ts files
    for root, dirs, files in os.walk(repo_path):
        for file in files:
            if file.endswith(('.py', '.js', '.ts')):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    # Only take first 2000 characters to avoid overly long prompts
                    excerpt = content[:2000]
                    
                    if not ("tools" in content or "prompts" in content or "resources" in content):
                        logging.info(f"Skipping file {file_path} as it does not contain tools, prompts, or resources.")
                        continue
                    
                    code_prompt = (
                        f"Analyze the following code file for indications of a Model Context Protocol (MCP) server implementation. "
                        f"Indications include returning a list of tools, prompts, or resources either via STDIO or HTTP SSE.\n"
                        f"---\n{excerpt}\n---\n"
                        f"Respond with 'MATCH' if the file contains such implementation, or 'NO_MATCH' otherwise."
                    )
                    logging.info(f"Analyzing code file for MCP indicators: {file_path}")
                    response = chat_client.complete(
                        temperature=0.2,
                        messages=[
                            {"role": "system", "content": "You are an AI assistant specialized in code analysis."},
                            {"role": "user", "content": code_prompt}
                        ]
                    )
                    analysis_result = response.choices[0].message.content.strip().upper()
                    if analysis_result == "MATCH":
                        rel_path = os.path.relpath(file_path, repo_path)
                        source_code_snippets.append(content)
                except Exception as e:
                    logging.warning(f"Failed processing file {file_path}: {e}")
    if source_code_snippets:
        source_code_summary = "\n".join(source_code_snippets)
    else:
        source_code_summary = "No source code indicators of MCP implementation detected."
    
    prompt = f"""
    Analyze the following repository content (primarily README.md) to determine if it describes a Model Context Protocol (MCP) server.

    Repository Path: {repo_path}

    README.md content:
    ---
    {readme_content[:4000]} 
    ---
    (Content might be truncated)

    Source Code Summary: {source_code_summary}

    Task:
    1. Determine if this repository implements an MCP server. This is ONLY true if you find explicit references a model context protcol service implementation.
    2. If it IS an MCP server, extract metadata conforming *exactly* to the 'server' object definition within the xregistry JSON schema (provided below). Pay close attention to required fields and data types.
    3. Extract information like 'name', 'description', 'mcpversion', 'serverversion', 'repository' details (if available beyond the clone URL), 'tools', 'resources', 'endpoints', 'deployment' details etc. from the README or other available context.
    4. If it is NOT an MCP server, respond with {{"is_mcp_server": false}}.
    5. If it IS an MCP server, respond ONLY with a single JSON object containing the extracted 'server' metadata, like this: {{"is_mcp_server": true, "server_data": {{...extracted server object...}} }}. Do not include any explanations outside the JSON structure.
    6. The returned JSON structure MUST NOT be wrapped in a code block

    xRegistry Server Schema Definition (for extraction reference):
    {{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "http://xregistry.io/schema/mcpproviders",
    "properties": {{
        "mcpproviders": {{
        "type": "object",
        "additionalProperties": {{
            "$ref": "#/definitions/mcpprovider"
            }}
            }}
        }},
        "definitions": {{
            "server": {{
            "type": "object",
            "properties": {{
                "serverid": {{
                "type": "string",
                "description": "ID of the server object"
                }},
                "name": {{
                "type": "string",
                "description": "Human-readable name of the MCP server."
                }},
                "epoch": {{
                "type": "integer",
                "description": "Epoch time of the object creation"
                }},
                "self": {{
                "type": "string",
                "format": "uri",
                "description": "URL of the object"
                }},
                "xid": {{
                "type": "string",
                "format": "xid",
                "description": "Relative URL of the object"
                }},
                "description": {{
                "type": "string",
                "description": "Short description of the server\u00e2\u20ac\u2122s purpose and capabilities."
                }},
                "documentation": {{
                "type": "string",
                "format": "uri",
                "description": "URI of the documentation of the object"
                }},
                "labels": {{
                "type": "object",
                "description": "Labels for the object"
                }},
                "createdat": {{
                "type": "string",
                "format": "date-time",
                "description": "Time of the object creation"
                }},
                "modifiedat": {{
                "type": "string",
                "format": "date-time",
                "description": "Time of the object modification"
                }},
                "mcpversion": {{
                "type": "string",
                "description": "The version of the MCP protocol that this server manifest conforms to."
                }},
                "serverversion": {{
                "type": "string",
                "description": "The version of this server implementation."
                }},
                "repository": {{
                "type": "object",
                "description": "Definition of the repository containing the server code.",
                "properties": {{
                    "url": {{
                    "type": "string",
                    "format": "uri",
                    "description": "The repository URL."
                    }},
                    "name": {{
                    "type": "string",
                    "description": "The repository name."
                    }},
                    "subfolder": {{
                    "type": "string",
                    "description": "Subfolder within the repository, if applicable."
                    }},
                    "branch": {{
                    "type": "string",
                    "description": "The branch to use."
                    }},
                    "commit": {{
                    "type": "string",
                    "description": "The specific commit hash."
                    }}
                }},
                "required": [
                    "url"
                ]
                }},
                "docs": {{
                "type": "string",
                "format": "uri",
                "description": "URI pointing to official external documentation for the server."
                }},
                "prompts": {{
                "type": "array",
                "description": "List of static, reusable prompt templates available in this server.",
                "items": {{
                    "type": "object",
                    "properties": {{
                    "name": {{
                        "type": "string",
                        "description": "Unique identifier for the prompt template."
                    }},
                    "description": {{
                        "type": "string",
                        "description": "Detailed explanation of when and how to use this prompt."
                    }},
                    "arguments": {{
                        "type": "array",
                        "items": {{
                        "type": "object",
                        "properties": {{
                            "name": {{
                            "type": "string",
                            "description": "Name of the argument."
                            }},
                            "description": {{
                            "type": "string",
                            "description": "Explanation of what this argument represents."
                            }},
                            "required": {{
                            "type": "boolean",
                            "description": "Whether this argument must be provided when invoking the prompt."
                            }}
                        }},
                        "required": [
                            "name"
                        ]
                        }}
                    }}
                    }},
                    "required": [
                    "name"
                    ]
                }}
                }},
                "tools": {{
                "type": "array",
                "description": "List of static tool definitions that can be invoked via the MCP runtime.",
                "items": {{
                    "type": "object",
                    "properties": {{
                    "name": {{
                        "type": "string",
                        "description": "Unique identifier for the tool."
                    }},
                    "description": {{
                        "type": "string",
                        "description": "Human-readable description of the tool\u00e2\u20ac\u2122s purpose."
                    }},
                    "inputschema": {{
                        "type": "object",
                        "description": "JSON Schema defining and validating the tool\u00e2\u20ac\u2122s input parameters.",
                        "properties": {{
                        "type": {{
                            "type": "string",
                            "description": "Schema type of the input definition."
                        }},
                        "properties": {{
                            "type": "object",
                            "description": "Map of property schemas."
                        }},
                        "required": {{
                            "type": "array",
                            "description": "List of required input fields.",
                            "items": {{
                            "type": "string"
                            }}
                        }},
                        "items": {{
                            "type": "object",
                            "description": "Schema for items when input is array.",
                            "properties": {{
                            "type": {{
                                "type": "string",
                                "description": "Type of the array items."
                            }},
                            "properties": {{
                                "type": "object",
                                "description": "Properties of each array item.",
                                "properties": {{}}
                            }},
                            "required": {{
                                "type": "array",
                                "description": "List of required fields in array items.",
                                "items": {{
                                "type": "string"
                                }}
                            }}
                            }}
                        }}
                        }},
                        "required": [
                        "type"
                        ]
                    }},
                    "annotations": {{
                        "type": "object",
                        "description": "Optional metadata annotations for tooling or documentation generators.",
                        "properties": {{}}
                    }}
                    }},
                    "required": [
                    "name",
                    "inputschema"
                    ]
                }}
                }},
                "resources": {{
                "type": "array",
                "description": "List of data resources the server can expose or subscribe to.",
                "items": {{
                    "type": "object",
                    "properties": {{
                    "uritemplate": {{
                        "type": "string",
                        "description": "URI template with placeholders (e.g. /resources/{{id}})."
                    }},
                    "name": {{
                        "type": "string",
                        "description": "Logical name for the resource type."
                    }},
                    "description": {{
                        "type": "string",
                        "description": "Explanation of how to fill the template parameters."
                    }},
                    "mimetype": {{
                        "type": "string",
                        "description": "MIME type of the resource payload."
                    }}
                    }},
                    "required": [
                    "uritemplate",
                    "name"
                    ]
                }}
                }},
                "endpoints": {{
                "type": "object",
                "description": "Configuration of transport endpoints for invoking the server over different protocols.",
                "properties": {{
                    "stdio": {{
                    "type": "object",
                    "description": "STDIO transport endpoint configuration.",
                    "properties": {{
                        "deployment": {{
                        "type": "string",
                        "description": "Deployment mode used for STDIO (must be 'sandbox')."
                        }}
                    }},
                    "required": [
                        "deployment"
                    ]
                    }},
                    "http": {{
                    "type": "object",
                    "description": "Public HTTP transport endpoint configuration.",
                    "properties": {{
                        "uri": {{
                        "type": "string",
                        "format": "uri",
                        "description": "Base URI for HTTP requests."
                        }},
                        "authorization": {{
                        "type": "object",
                        "description": "Authorization configuration for HTTP endpoint.",
                        "properties": {{
                            "type": {{
                            "type": "string",
                            "description": "Authorization scheme type (e.g., header, PLAIN)."
                            }},
                            "name": {{
                            "type": "string",
                            "description": "Name of the header or field carrying credentials."
                            }},
                            "description": {{
                            "type": "string",
                            "description": "Explanation of how to provide credentials."
                            }},
                            "required": {{
                            "type": "boolean",
                            "description": "Whether credentials are mandatory for access."
                            }},
                            "format": {{
                            "type": "string",
                            "description": "Template for credential format (e.g., Bearer {{token}})."
                            }},
                            "username": {{
                            "type": "object",
                            "description": "Configuration for username in PLAIN auth.",
                            "properties": {{
                                "description": {{
                                "type": "string"
                                }},
                                "required": {{
                                "type": "boolean"
                                }}
                            }}
                            }},
                            "password": {{
                            "type": "object",
                            "description": "Configuration for password in PLAIN auth.",
                            "properties": {{
                                "description": {{
                                "type": "string"
                                }},
                                "required": {{
                                "type": "boolean"
                                }}
                            }}
                            }}
                        }},
                        "required": [
                            "type",
                            "required"
                        ]
                        }},
                        "openapi": {{
                        "type": "object",
                        "description": "Reference to an OpenAPI specification document.",
                        "properties": {{
                            "url": {{
                            "type": "string",
                            "format": "uri",
                            "description": "URL where the OpenAPI JSON or YAML can be retrieved."
                            }},
                            "description": {{
                            "type": "string",
                            "description": "Human-readable summary of the OpenAPI document\u00e2\u20ac\u2122s coverage."
                            }}
                        }},
                        "required": [
                            "url"
                        ]
                        }}
                    }},
                    "required": [
                        "uri",
                        "authorization"
                    ]
                    }},
                    "websockets": {{
                    "type": "object",
                    "description": "WebSocket transport endpoint configuration.",
                    "properties": {{
                        "uri": {{
                        "type": "string",
                        "format": "uri",
                        "description": "WebSocket URI for bidirectional communication."
                        }},
                        "authorization": {{
                        "type": "object",
                        "description": "Authorization configuration for WebSockets endpoint.",
                        "properties": {{
                            "type": {{
                            "type": "string",
                            "description": "Authorization scheme type."
                            }},
                            "name": {{
                            "type": "string"
                            }},
                            "description": {{
                            "type": "string"
                            }},
                            "required": {{
                            "type": "boolean"
                            }},
                            "format": {{
                            "type": "string"
                            }},
                            "username": {{
                            "type": "object",
                            "properties": {{
                                "description": {{
                                "type": "string"
                                }},
                                "required": {{
                                "type": "boolean"
                                }}
                            }}
                            }},
                            "password": {{
                            "type": "object",
                            "properties": {{
                                "description": {{
                                "type": "string"
                                }},
                                "required": {{
                                "type": "boolean"
                                }}
                            }}
                            }}
                        }},
                        "required": [
                            "type",
                            "required"
                        ]
                        }}
                    }},
                    "required": [
                        "uri",
                        "authorization"
                    ]
                    }},
                    "mqtt": {{
                    "type": "object",
                    "description": "MQTT transport endpoint configuration.",
                    "properties": {{
                        "uri": {{
                        "type": "string",
                        "description": "MQTT broker URI for publish/subscribe."
                        }},
                        "authorization": {{
                        "type": "object",
                        "description": "Authorization configuration for MQTT endpoint.",
                        "properties": {{
                            "type": {{
                            "type": "string",
                            "description": "Authorization scheme type."
                            }},
                            "name": {{
                            "type": "string"
                            }},
                            "description": {{
                            "type": "string"
                            }},
                            "required": {{
                            "type": "boolean"
                            }},
                            "format": {{
                            "type": "string"
                            }},
                            "username": {{
                            "type": "object",
                            "properties": {{
                                "description": {{
                                "type": "string"
                                }},
                                "required": {{
                                "type": "boolean"
                                }}
                            }}
                            }},
                            "password": {{
                            "type": "object",
                            "properties": {{
                                "description": {{
                                "type": "string"
                                }},
                                "required": {{
                                "type": "boolean"
                                }}
                            }}
                            }}
                        }},
                        "required": [
                            "type",
                            "required"
                        ]
                        }}
                    }},
                    "required": [
                        "uri",
                        "authorization"
                    ]
                    }},
                    "httplocal": {{
                    "type": "object",
                    "description": "Local HTTP transport endpoint configuration.",
                    "properties": {{
                        "deployment": {{
                        "type": "string",
                        "description": "Deployment mode for local HTTP (must be 'container')."
                        }},
                        "port": {{
                        "type": "integer",
                        "description": "TCP port on which the server listens locally."
                        }},
                        "host": {{
                        "type": "string",
                        "description": "Hostname or IP address for local binding."
                        }},
                        "protocol": {{
                        "type": "string",
                        "description": "Protocol scheme for local HTTP (e.g., 'http')."
                        }}
                    }},
                    "required": [
                        "deployment",
                        "port",
                        "host",
                        "protocol"
                    ]
                    }}
                }}
                }},
                "deployment": {{
                "type": "object",
                "description": "Deployment configurations for running the server in container or sandbox environments.",
                "properties": {{
                    "container": {{
                    "type": "object",
                    "properties": {{
                        "image": {{
                        "type": "string",
                        "description": "Name (and optionally tag) of the Docker image."
                        }},
                        "args": {{
                        "type": "array",
                        "items": {{
                            "type": "string"
                        }}
                        }},
                        "env": {{
                        "type": "array",
                        "items": {{
                            "type": "object",
                            "properties": {{
                            "name": {{
                                "type": "string"
                            }},
                            "description": {{
                                "type": "string"
                            }},
                            "required": {{
                                "type": "boolean"
                            }},
                            "default": {{
                                "type": "string"
                            }}
                            }}
                        }}
                        }}
                    }},
                    "required": [
                        "image"
                    ]
                    }},
                    "sandbox": {{
                    "type": "object",
                    "properties": {{
                        "runtime": {{
                        "type": "string",
                        "description": "Type of sandbox runtime."
                        }},
                        "package": {{
                        "type": "string",
                        "description": "NPM package name."
                        }},
                        "packageversion": {{
                        "type": "string",
                        "description": "Optional fixed version of the NPM package."
                        }},
                        "command": {{
                        "type": "string",
                        "description": "CLI command to invoke."
                        }},
                        "args": {{
                        "type": "array",
                        "items": {{
                            "type": "string"
                        }}
                        }},
                        "env": {{
                        "type": "array",
                        "items": {{
                            "type": "object",
                            "properties": {{
                            "name": {{
                                "type": "string"
                            }},
                            "description": {{
                                "type": "string"
                            }},
                            "required": {{
                                "type": "boolean"
                            }},
                            "default": {{
                                "type": "string"
                            }}
                            }}
                        }}
                        }}
                    }},
                    "required": [
                        "runtime",
                        "package",
                        "command"
                    ]
                    }}
                }}
                }}
            }},
            "required": [
                "mcpversion",
                "serverversion",
                "name",
                "deployment"
            ]
            }},
            "mcpprovider": {{
            "type": "object",
            "properties": {{
                "mcpproviderid": {{
                "type": "string",
                "description": "ID of the mcpprovider object"
                }},
                "name": {{
                "type": "string",
                "description": "Name of the object"
                }},
                "epoch": {{
                "type": "integer",
                "description": "Epoch time of the object creation"
                }},
                "self": {{
                "type": "string",
                "format": "uri",
                "description": "URL of the object"
                }},
                "xid": {{
                "type": "string",
                "format": "xid",
                "description": "Relative URL of the object"
                }},
                "description": {{
                "type": "string",
                "description": "Description of the object"
                }},
                "documentation": {{
                "type": "string",
                "format": "uri",
                "description": "URI of the documentation of the object"
                }},
                "labels": {{
                "type": "object",
                "description": "Labels for the object"
                }},
                "createdat": {{
                "type": "string",
                "format": "date-time",
                "description": "Time of the object creation"
                }},
                "modifiedat": {{
                "type": "string",
                "format": "date-time",
                "description": "Time of the object modification"
                }},
                "servers": {{
                "type": "object",
                "additionalProperties": {{
                    "$ref": "#/definitions/server"
                }}
                }}
            }}
            }}
        }}
    }}

    Respond ONLY with the JSON object.
    """

    # initialize completion to avoid undefined variable on exception
    completion = ""
    try:
        # Retry on transient failures
        for attempt in range(3):
            try:
                response = chat_client.complete(
                    temperature=0.2,
                    messages=[
                        {"role": "system", "content": "You are an AI assistant specialized in extracting structured metadata."},
                        {"role": "user", "content": prompt}
                    ]
                )
            
                completion = response.choices[0].message.content
                logging.info("Received response from Azure AI.")
                try:
                    llm_data = json.loads(completion)

                    if isinstance(llm_data, dict) and llm_data.get("is_mcp_server") is True:
                        server_data = llm_data.get("server_data")
                        if isinstance(server_data, dict):
                            # Basic validation - check for some required fields
                            if all(key in server_data for key in ["name", "mcpversion", "serverversion"]):
                                logging.info("Successfully extracted MCP server metadata.")
                                return server_data
                            else:
                                logging.warning("LLM response marked as MCP server but missing required fields in server_data.")
                                return None
                        else:
                            logging.warning("LLM response marked as MCP server but 'server_data' is not a valid object.")
                    elif isinstance(llm_data, dict) and llm_data.get("is_mcp_server") is False:
                        logging.info("LLM determined repository is NOT an MCP server.")
                        return None
                    else:
                        logging.warning(f"LLM response did not follow the expected format: {completion}")
                except json.JSONDecodeError as e:
                    logging.error(f"Failed to decode JSON response from LLM: {e}")
                    logging.error(f"LLM Raw Output was: {completion}")
                    raise e
            except Exception as e:
                logging.warning(f"Chat completion attempt {attempt+1} failed: {e}")
                if attempt == 2:
                    logging.error("All chat completion attempts failed.")
                    return None
    except Exception as e:
        logging.error(f"Error interacting with Azure OpenAI: {e}", exc_info=True)
        return None


def process_repository(repo_info: dict, chat_client: ChatCompletionsClient) -> None:
    """
    Clones a repository, analyzes it using an LLM, and saves the metadata if it's an MCP server.
    """
    repo_url = repo_info.get('repository', {}).get('url')
    repo_name_full = repo_info.get('repository', {}).get('name') # e.g., "org/repo"
    subfolder = repo_info.get('repository', {}).get('subfolder', '')
    
    org_name, repo_name = repo_name_full.split('/', 1)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_out = os.path.join(script_dir, OUTPUT_DIR_BASE)
    output_dir = os.path.join(base_out, org_name, 'servers', repo_name)
    
    if os.path.exists(output_dir):
        logging.info(f"Output directory already exists, skipping: {output_dir}")
        return

    if not repo_url or not repo_name_full:
        logging.warning(f"Skipping entry due to missing repository URL or name: {repo_info.get('name')}")
        return

    if '/' not in repo_name_full:
        logging.warning(f"Skipping entry due to invalid repository name format (expected 'org/repo'): {repo_name_full}")
        return

    logging.info(f"Processing repository: {repo_name_full} ({repo_url})")

    temp_dir = tempfile.mkdtemp(prefix="mcp_repo_")
    logging.info(f"Cloning into temporary directory: {temp_dir}")

    try:
        # Clone only the default branch, shallow clone for speed
        subprocess.run(['git', 'clone', '--depth', '1', repo_url, temp_dir], check=True, capture_output=True, text=True)
        logging.info(f"Successfully cloned {repo_name_full}")

        # Determine the path to analyze (either root or subfolder)
        analysis_path = os.path.join(temp_dir, subfolder) if subfolder else temp_dir
        if not os.path.isdir(analysis_path):
             logging.error(f"Subfolder '{subfolder}' not found in cloned repo {repo_name_full}")
             return # Skip if subfolder doesn't exist

        # Analyze using LLM
        server_metadata = get_repo_metadata_with_llm(analysis_path, chat_client)

        if server_metadata:
            # Ensure repository details from seed are included/updated if missing from LLM output
            if 'repository' not in server_metadata:
                server_metadata['repository'] = {}
            server_metadata['repository']['url'] = repo_info.get('repository', {}).get('url', repo_url)
            server_metadata['repository']['name'] = repo_info.get('repository', {}).get('name', repo_name_full)
            if subfolder:
                 server_metadata['repository']['subfolder'] = subfolder
            # Add other known info if needed (e.g., id, name from seed?) - requires schema clarification

            # anchor output to script directory            
            output_path = os.path.join(output_dir, 'index.json')

            logging.info(f"Writing MCP server metadata to: {output_path}")
            os.makedirs(output_dir, exist_ok=True)

            # Write the extracted server metadata object directly
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(server_metadata, f, indent=2)

    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to clone repository {repo_url}: {e}")
        logging.error(f"Git stderr: {e.stderr}")
    except Exception as e:
        logging.error(f"An unexpected error occurred processing {repo_name_full}: {e}", exc_info=True)
    finally:
        # Clean up the temporary directory
        if os.path.exists(temp_dir):
            logging.info(f"Cleaning up temporary directory: {temp_dir}")
            shutil.rmtree(temp_dir, ignore_errors=True)


def get_subscription_id() -> str:
    # prefer env var
    sub = os.getenv("AZURE_SUBSCRIPTION_ID")
    if sub:
        return sub
    # fallback to Azure CLI
    try:
        result = subprocess.run(
            "az account show --query id -o tsv",
            shell=True, capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except Exception as e:
        logging.error("AZURE_SUBSCRIPTION_ID not set and 'az account show' failed: %s", e)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Process MCP repositories using Azure AI.")
    parser.add_argument('--provision', action='store_true', help='Provision Azure AI Foundry resources using defaults')
    parser.add_argument('--deprovision', action='store_true', help='Deprovision Azure AI Foundry resources using defaults')
    parser.add_argument('--delete-rg', action='store_true', help='Also delete the resource group when deprovisioning')
    args = parser.parse_args()

    # derive subscription ID
    subscription_id = get_subscription_id()
    rg_name = DEFAULT_RESOURCE_GROUP_NAME
    location = DEFAULT_AZURE_LOCATION
    project_name = DEFAULT_AI_PROJECT_NAME
    deployment_name = DEFAULT_AOAI_DEPLOYMENT_NAME
    model_name = DEFAULT_AOAI_MODEL_NAME

    if args.provision:
        provision_resources(subscription_id, rg_name, location, project_name, deployment_name, model_name)
        sys.exit(0)
    if args.deprovision:
        deprovision_resources(subscription_id, rg_name, project_name, deployment_name, args.delete_rg)
        sys.exit(0)

    if not os.path.exists(SEED_FILE):
        logging.error(f"Seed file not found: {SEED_FILE}")
        return

    try:
        with open(SEED_FILE, 'r', encoding='utf-8') as f:
            # assume valid JSON list; strip only // comments
            raw = f.read()
        try:
            seed_data = json.loads(raw)
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse seed file after cleaning comments: {e}")
            return

        if not isinstance(seed_data, list):
            logging.error(f"Seed file content is not a JSON list: {SEED_FILE}")
            return

        logging.info(f"Successfully loaded {len(seed_data)} entries from {SEED_FILE}")
        
        # Initialize chat client for analyzing individual code files
        chat_client = get_chat_client(rg_name)

        for entry in seed_data:
            if isinstance(entry, dict) and 'repository' in entry:
                process_repository(
                    entry,
                    chat_client
                )
            else:
                 logging.debug(f"Skipping entry without repository information: {entry}")


    except json.JSONDecodeError as e:
        logging.error(f"Failed to parse seed file {SEED_FILE}: {e}")
    except Exception as e:
        logging.error(f"An error occurred during processing: {e}", exc_info=True)

if __name__ == "__main__":
    main()
