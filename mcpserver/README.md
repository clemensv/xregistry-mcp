# xRegistry-MCP Server

This repository contains the implementation of the xRegistry-MCP Server, which interacts with a remote registry to manage MCP providers, servers, tools, resources, prompts, and deployments.

## Overview

The server is built using the Model Context Protocol (MCP) SDK, and it provides the following functionalities:
- **Configuration & Setup:** 
  - Defines server metadata (name and version).
  - Loads FlexSearch indexes for efficient keyword-based searches.
  - Maintains a connection with the remote registry hosted at `https://clemensv.github.io/xregistry-mcp/`.

- **Tool Endpoints:**
  - **GET_PROVIDERS:** Returns all available MCP providers.
  - **GET_SERVERS:** Retrieves servers associated with a specific provider.
  - **FIND_SERVERS:** Searches for servers using keywords.
  - **FIND_TOOLS:** Searches for tools using keywords.
  - **FIND_PROMPTS:** Searches for prompts using keywords.
  - **FIND_RESOURCES:** Searches for resources using keywords.
  - **FIND_DEPLOYMENTS:** Searches for deployments (assumed to be part of server results).

- **Prompt Endpoints:**
  - **MCP_MANIFEST:** Retrieves the MCP manifest.
  - **MCP_SERVER_REGISTRATION:** Registers a new MCP server.

## Technical Details

1. **Server Initialization:**
   - The server initializes with a name ("xRegistry-MCP-Server") and version ("1.0.0").
   - It registers capabilities for prompts, tools, and logging.

2. **Data Indexing & Searching:**
   - Uses [FlexSearch](https://github.com/nextapps-de/flexsearch) to create indexes for `server`, `tool`, `resource`, and `prompt`.
   - Index JSON files are fetched from the remote registry URL and imported into FlexSearch.

3. **Request Handlers:**
   - **List Tools & Prompts:** Define the available tools and prompts with descriptions and input schema for each.
   - **Call Tool:** Handles tool calls by processing requests, fetching data from the registry, and performing searches on the imported indexes.

4. **Registry Data Fetching:**
   - Data fetching is abstracted into a helper function that retrieves JSON data from the remote registry URL.
   - Algorithms are in place to manage communication failures.

5. **Cleanup:**
   - The server includes a cleanup function for resource management (e.g., closing connections).

## Usage

1. **Starting the Server:**
   - Instantiate the server by invoking the `createServer` function.
   - Ensure that the machine has network access to fetch remote index data.

2. **Interacting with the Server:**
   - Use the tool endpoints to retrieve or search for MCP providers, servers, tools, resources, prompts, or deployments.
   - Use the prompt endpoints to interact with the MCP manifest and server registration.

3. **Extending the Server:**
   - Additional handlers can be added to extend functionalities further.
   - Modify the FlexSearch configurations or fetch behavior as required.

## Repository Structure

```
/mcpserver
 ├── registry.ts      # Main server implementation using MCP SDK
 ├── README.md        # Project documentation (this file)
```

## Dependencies

- [@modelcontextprotocol/sdk](https://www.npmjs.com/package/@modelcontextprotocol/sdk)
- [zod](https://github.com/colinhacks/zod) for schema validation
- [node-fetch](https://www.npmjs.com/package/node-fetch) for HTTP requests
- [FlexSearch](https://github.com/nextapps-de/flexsearch) for indexing and search functionality

## Conclusion

The xRegistry-MCP Server is a lightweight yet powerful registry system designed for efficient management and searching of MCP entities. This design allows for dynamic data retrieval from remote sources, flexibility in search operations, and easy integration with MCP-based workflows.