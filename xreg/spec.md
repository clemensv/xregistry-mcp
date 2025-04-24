# MCP Providers Registry Service - Version 1.0-rc1

## Abstract

This specification defines an MCP (Model Context Protocol) Providers registry
extension to the xRegistry document format and API
[specification](../core/spec.md).

## Table of Contents

- [MCP Providers Registry Service - Version 1.0-rc1](#mcp-providers-registry-service---version-10-rc1)
  - [Abstract](#abstract)
  - [Table of Contents](#table-of-contents)
  - [Overview](#overview)
  - [Notations and Terminology](#notations-and-terminology)
    - [Notational Conventions](#notational-conventions)
    - [Terminology](#terminology)
      - [MCP Server](#mcp-server)
      - [MCP Provider](#mcp-provider)
      - [Registry Group (`mcpproviders`)](#registry-group-mcpproviders)
      - [Registry Resource (`servers`)](#registry-resource-servers)
  - [MCP Providers Registry](#mcp-providers-registry)
  - [MCP Providers Registry Model](#mcp-providers-registry-model)
    - [MCP Provider Group (`mcpproviders`)](#mcp-provider-group-mcpproviders)
    - [Server Resource (`servers`)](#server-resource-servers)
      - [`mcpversion`](#mcpversion)
      - [`serverversion`](#serverversion)
      - [`name`](#name)
      - [`description`](#description)
      - [`repository`](#repository)
      - [`docs`](#docs)
      - [`prompts`](#prompts)
      - [`tools`](#tools)
      - [`resources`](#resources)
      - [`endpoints`](#endpoints)
      - [`deployment`](#deployment)
  - [Example: MCP Providers Registry Model](#example-mcp-providers-registry-model)


## Overview

This specification defines an MCP Providers registry extension to the xRegistry
document format and API [specification](../core/spec.md). The purpose of this
registry is to provide a machine-readable catalog of available MCP servers,
their capabilities, configuration, and deployment details.

MCP servers act as proxies or gateways that compose functionality from various
backend models or services. This registry allows clients and orchestration
systems to discover and interact with these servers in a standardized way.

## Notations and Terminology

### Notational Conventions

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD",
"SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be
interpreted as described in [RFC 2119](https://tools.ietf.org/html/rfc2119).

For clarity, OPTIONAL attributes (specification-defined and extensions) are
OPTIONAL for clients to use, but the servers' responsibility will vary.
Server-unknown extension attributes MUST be silently stored in the backing
datastore. Specification-defined, and server-known extension, attributes MUST
generate an error if corresponding feature is not supported or enabled. However,
as with all attributes, if accepting the attribute would result in a bad state
(such as exceeding a size limit, or results in a security issue), then the
server MAY choose to reject the request.

In the pseudo JSON format snippets `?` means the preceding attribute is
OPTIONAL, `*` means the preceding attribute MAY appear zero or more times, and
`+` means the preceding attribute MUST appear at least once. The presence of the
`#` character means the remaining portion of the line is a comment. Whitespace
characters in the JSON snippets are used for readability and are not normative.

### Terminology

This specification defines the following terms:

#### MCP Server

An **MCP Server** is an application conforming to the MCP protocol
specification, acting as a proxy or facade to one or more underlying AI models
or services. It exposes capabilities like prompts, tools, and resources through
defined endpoints.

#### MCP Provider

An **MCP Provider** represents the entity or organization publishing an MCP
Server definition.

#### Registry Group (`mcpproviders`)

A logical grouping within the xRegistry specific to MCP provider definitions.

#### Registry Resource (`servers`)

A specific definition of an MCP Server within the `mcpproviders` group,
detailing its attributes, capabilities, and deployment information.

## MCP Providers Registry

The MCP Providers Registry is a catalog of MCP Server definitions. Entries
describe the server's metadata, capabilities (prompts, tools, resources),
endpoints for interaction, and deployment configurations.

This registry enables:
- Discovery of available MCP servers.
- Understanding server capabilities and interaction protocols.
- Automated deployment and configuration of MCP servers.

All MCP Server definitions MUST be defined within the `mcpproviders` group.

## MCP Providers Registry Model

The formal xRegistry extension model for the MCP Providers Registry resides in
the [model.json](model.json) file (sibling to this document).

### MCP Provider Group (`mcpproviders`)

- **Group Name (GROUP):** `mcpproviders`
- **Singular Type:** `mcpprovider`
- **Plural Type:** `mcpproviders`
- **Description:** Contains definitions for MCP Servers provided by various
  entities.

This group acts as the container for all `servers` resources defined according
to this specification.

### Server Resource (`servers`)

- **Resource Collection Name:** `servers` (within the `mcpproviders` group)
- **Singular Type:** `server`
- **Plural Type:** `servers`
- **Description:** Defines a specific MCP Server instance, its capabilities,
  endpoints, and deployment details.

The following attributes are defined for the `server` resource in addition to
the xRegistry-defined core
[attributes](../core/spec.md#attributes-and-extensions):

#### `mcpversion`

- **Type:** `string`
- **Description:** The version of the MCP protocol that this server manifest
  conforms to.
- **Constraints:** REQUIRED. Must be a non-empty string.

#### `serverversion`

- **Type:** `string`
- **Description:** The version of this server implementation.
- **Constraints:** REQUIRED. Must be a non-empty string.

#### `name`

- **Type:** `string`
- **Description:** Human-readable name of the MCP server.
- **Constraints:** REQUIRED. Must be a non-empty string.

#### `description`

- **Type:** `string`
- **Description:** Short description of the server’s purpose and capabilities.
- **Constraints:** OPTIONAL.

#### `repository`

- **Type:** `object`
- **Description:** Definition of the repository containing the server code.
- **Constraints:** OPTIONAL.
- **Attributes:**
    - `url` (Type: `uri`, REQUIRED): The repository URL.
    - `name` (Type: `string`, OPTIONAL): The repository name.
    - `subfolder` (Type: `string`, OPTIONAL): Subfolder within the repository,
      if applicable.
    - `branch` (Type: `string`, OPTIONAL): The branch to use.
    - `commit` (Type: `string`, OPTIONAL): The specific commit hash.

#### `docs`

- **Type:** `uri`
- **Description:** URI pointing to official external documentation for the
  server.
- **Constraints:** OPTIONAL. Must be a valid URI.

#### `prompts`

- **Type:** `array`
- **Description:** List of static, reusable prompt templates available in this
  server.
- **Constraints:** OPTIONAL.
- **Item Schema:** `object`
    - **Attributes:**
        - `name` (Type: `string`, REQUIRED): Unique identifier for the prompt
          template.
        - `description` (Type: `string`, OPTIONAL): Detailed explanation of when
          and how to use this prompt.
        - `arguments` (Type: `array`, OPTIONAL): List of arguments the prompt
          template accepts.
            - **Item Schema:** `object`
                - **Attributes:**
                    - `name` (Type: `string`, REQUIRED): Name of the argument.
                    - `description` (Type: `string`, OPTIONAL): Explanation of
                      what this argument represents.
                    - `required` (Type: `boolean`, REQUIRED, Default: `false`):
                      Whether this argument must be provided when invoking the
                      prompt.

#### `tools`

- **Type:** `array`
- **Description:** List of static tool definitions that can be invoked via the
  MCP runtime.
- **Constraints:** OPTIONAL.
- **Item Schema:** `object`
    - **Attributes:**
        - `name` (Type: `string`, REQUIRED): Unique identifier for the tool.
        - `description` (Type: `string`, OPTIONAL): Human-readable description
          of the tool’s purpose.
        - `inputschema` (Type: `object`, REQUIRED): JSON Schema defining and
          validating the tool’s input parameters.
        - `annotations` (Type: `object`, OPTIONAL): Optional metadata
          annotations for tooling or documentation generators.

#### `resources`

- **Type:** `array`
- **Description:** List of data resources the server can expose or subscribe to.
- **Constraints:** OPTIONAL.
- **Item Schema:** `object`
    - **Attributes:**
        - `uritemplate` (Type: `string`, REQUIRED): URI template with
          placeholders (e.g. `/resources/{id}`).
        - `name` (Type: `string`, REQUIRED): Logical name for the resource type.
        - `description` (Type: `string`, OPTIONAL): Explanation of how to fill
          the template parameters.
        - `mimetype` (Type: `string`, OPTIONAL): MIME type of the resource
          payload.

#### `endpoints`

- **Type:** `object`
- **Description:** Configuration of transport endpoints for invoking the server
  over different protocols.
- **Constraints:** OPTIONAL.
- **Attributes:** (Each endpoint type is an OPTIONAL object)
    - `stdio`: STDIO transport endpoint configuration.
        - `deployment` (Type: `string`, REQUIRED, Enum: `["sandbox"]`):
          Deployment mode.
    - `http`: Public HTTP transport endpoint configuration.
        - `uri` (Type: `uri`, REQUIRED): Base URI for HTTP requests.
        - `authorization` (Type: `object`, REQUIRED): Authorization
          configuration.
            - `type` (Type: `string`, REQUIRED): Scheme type (e.g., `header`,
              `PLAIN`).
            - `name` (Type: `string`, OPTIONAL): Header/field name for
              credentials.
            - `description` (Type: `string`, OPTIONAL): How to provide
              credentials.
            - `required` (Type: `boolean`, REQUIRED): If credentials are
              mandatory.
            - `format` (Type: `string`, OPTIONAL): Credential format template
              (e.g., `Bearer {token}`).
            - `username` (Type: `object`, OPTIONAL): PLAIN auth username config
              (`description`, `required`).
            - `password` (Type: `object`, OPTIONAL): PLAIN auth password config
              (`description`, `required`).
        - `openapi` (Type: `object`, OPTIONAL): Reference to an OpenAPI
          specification.
            - `url` (Type: `uri`, REQUIRED): URL of the OpenAPI document.
            - `description` (Type: `string`, OPTIONAL): Summary of the OpenAPI
              document.
    - `websockets`: WebSocket transport endpoint configuration.
        - `uri` (Type: `uri`, REQUIRED): WebSocket URI.
        - `authorization` (Type: `object`, REQUIRED): Authorization
          configuration (structure similar to HTTP).
    - `mqtt`: MQTT transport endpoint configuration.
        - `uri` (Type: `string`, REQUIRED): MQTT broker URI.
        - `authorization` (Type: `object`, REQUIRED): Authorization
          configuration (structure similar to HTTP).
    - `httplocal`: Local HTTP transport endpoint configuration.
        - `deployment` (Type: `string`, REQUIRED, Enum: `["container"]`):
          Deployment mode.
        - `port` (Type: `integer`, REQUIRED): Local TCP port.
        - `host` (Type: `string`, REQUIRED): Local hostname/IP.
        - `protocol` (Type: `string`, REQUIRED): Local protocol scheme (e.g.,
          `http`).

#### `deployment`

- **Type:** `object`
- **Description:** Deployment configurations for running the server in container
  or sandbox environments.
- **Constraints:** REQUIRED.
- **Attributes:** (At least one deployment type MUST be present)
    - `container` (Type: `object`, OPTIONAL): Configuration for container-based
      deployment.
        - `image` (Type: `string`, REQUIRED): Docker image name (and optional
          tag).
        - `args` (Type: `array` of `string`, OPTIONAL): Container arguments.
        - `env` (Type: `array` of `object`, OPTIONAL): Environment variables.
            - Item Attributes: `name` (string), `description` (string),
              `required` (boolean), `default` (string).
    - `sandbox` (Type: `object`, OPTIONAL): Configuration for sandbox-based
      deployment.
        - `runtime` (Type: `string`, REQUIRED): Type of sandbox runtime.
        - `package` (Type: `string`, REQUIRED): NPM package name.
        - `packageversion` (Type: `string`, OPTIONAL): Fixed NPM package
          version.
        - `command` (Type: `string`, REQUIRED): CLI command to invoke.
        - `args` (Type: `array` of `string`, OPTIONAL): Command arguments.
        - `env` (Type: `array` of `object`, OPTIONAL): Environment variables
          (same structure as container env).


## Example: MCP Providers Registry Model

The following example defines a registry model for MCP providers, with a single
`mcpproviders` group and a `servers` resource:

```json
{
  "groups": {
    "mcpproviders": {
      "plural": "mcpproviders",
      "singular": "mcpprovider",
      "resources": {
        "servers": {
          "plural": "servers",
          "singular": "server",
          "maxversions": 1,
          "setversionid": false,
          "setdefaultversionsticky": false,
          "hasdocument": false,
          "singleversionroot": true,
          "labels": {},
          "attributes": {
            "mcpversion": { "name": "mcpversion", "type": "string", "description": "The version of the MCP protocol that this server manifest conforms to.", "required": true },
            "serverversion": { "name": "serverversion", "type": "string", "description": "The version of this server implementation.", "required": true },
            "name": { "name": "name", "type": "string", "description": "Human-readable name of the MCP server.", "required": true },
            "description": { "name": "description", "type": "string", "description": "Short description of the server’s purpose and capabilities." },
            "repository": {
              "name": "repository", "type": "object", "description": "Definition of the repository containing the server code.",
              "attributes": {
                "url": { "name": "url", "type": "uri", "description": "The repository URL.", "required": true },
                "name": { "name": "name", "type": "string", "description": "The repository name." },
                "subfolder": { "name": "subfolder", "type": "string", "description": "Subfolder within the repository, if applicable." },
                "branch": { "name": "branch", "type": "string", "description": "The branch to use." },
                "commit": { "name": "commit", "type": "string", "description": "The specific commit hash." }
              }
            },
            "docs": { "name": "docs", "type": "uri", "description": "URI pointing to official external documentation for the server." },
            "prompts": {
              "name": "prompts", "type": "array", "description": "List of static, reusable prompt templates available in this server.",
              "item": {
                "type": "object", "attributes": {
                  "name": { "name": "name", "type": "string", "description": "Unique identifier for the prompt template.", "required": true },
                  "description": { "name": "description", "type": "string", "description": "Detailed explanation of when and how to use this prompt." },
                  "arguments": { "name": "arguments", "type": "array",
                    "item": { "type": "object", "attributes": {
                      "name": { "name": "name", "type": "string", "description": "Name of the argument.", "required": true },
                      "description": { "name": "description", "type": "string", "description": "Explanation of what this argument represents." },
                      "required": { "name": "required", "type": "boolean", "description": "Whether this argument must be provided when invoking the prompt.", "required": true, "default": false }
                    }}
                  }
                }
              }
            },
            "tools": {
              "name": "tools", "type": "array", "description": "List of static tool definitions that can be invoked via the MCP runtime.",
              "item": { "type": "object", "attributes": {
                "name": { "name": "name", "type": "string", "description": "Unique identifier for the tool.", "required": true },
                "description": { "name": "description", "type": "string", "description": "Human-readable description of the tool’s purpose." },
                "inputschema": { "name": "inputschema", "type": "object", "description": "JSON Schema defining and validating the tool’s input parameters.", "required": true },
                "annotations": { "name": "annotations", "type": "object", "description": "Optional metadata annotations for tooling or documentation generators." }
              }}
            },
            "resources": {
              "name": "resources", "type": "array", "description": "List of data resources the server can expose or subscribe to.",
              "item": { "type": "object", "attributes": {
                "uritemplate": { "name": "uritemplate", "type": "string", "description": "URI template with placeholders (e.g. /resources/{id}).", "required": true },
                "name": { "name": "name", "type": "string", "description": "Logical name for the resource type.", "required": true },
                "description": { "name": "description", "type": "string", "description": "Explanation of how to fill the template parameters." },
                "mimetype": { "name": "mimetype", "type": "string", "description": "MIME type of the resource payload." }
              }}
            },
            "endpoints": {
              "name": "endpoints",
              "type": "object",
              "description": "Configuration of transport endpoints for invoking the server over different protocols.",
              "attributes": {
                "stdio": { "name": "stdio", "type": "object", "description": "STDIO transport endpoint configuration.", "attributes": { "deployment": { "name": "deployment", "type": "string", "description": "Deployment mode used for STDIO (must be 'sandbox').", "required": true, "enum": ["sandbox"] } } },
                "http": { "name": "http", "type": "object", "description": "Public HTTP transport endpoint configuration.", "attributes": { "uri": { "name": "uri", "type": "uri", "description": "Base URI for HTTP requests.", "required": true }, "authorization": { "$ref": "#/definitions/Authorization" }, "openapi": { "$ref": "#/definitions/OpenApiSpec" } } },
                "websockets": { "name": "websockets", "type": "object", "description": "WebSocket transport endpoint configuration.", "attributes": { "uri": { "name": "uri", "type": "uri", "description": "WebSocket URI for bidirectional communication.", "required": true }, "authorization": { "$ref": "#/definitions/Authorization" } } },
                "mqtt": { "name": "mqtt", "type": "object", "description": "MQTT transport endpoint configuration.", "attributes": { "uri": { "name": "uri", "type": "string", "description": "MQTT broker URI for publish/subscribe.", "required": true }, "authorization": { "$ref": "#/definitions/Authorization" } } },
                "httplocal": { "name": "httplocal", "type": "object", "description": "Local HTTP transport endpoint configuration.", "attributes": { "deployment": { "name": "deployment", "type": "string", "description": "Deployment mode for local HTTP (must be 'container').", "required": true, "enum": ["container"] }, "port": { "name": "port", "type": "integer", "description": "TCP port on which the server listens locally.", "required": true }, "host": { "name": "host", "type": "string", "description": "Hostname or IP address for local binding.", "required": true }, "protocol": { "name": "protocol", "type": "string", "description": "Protocol scheme for local HTTP (e.g., 'http').", "required": true } } }
              }
            },
            "deployment": {
              "name": "deployment",
              "type": "object",
              "description": "Deployment configurations for running the server in container or sandbox environments.",
              "required": true,
              "attributes": {
                "container": { "$ref": "#/definitions/DeploymentContainer" },
                "sandbox": { "$ref": "#/definitions/DeploymentSandbox" }
              }
            }
          }
        }
      }
    }
  }
}
```

[RFC 2119]: https://tools.ietf.org/html/rfc2119
