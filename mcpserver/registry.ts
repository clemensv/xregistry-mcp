import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  ListPromptsRequestSchema,
  LoggingLevel,
} from "@modelcontextprotocol/sdk/types.js";
import { z } from "zod";
import fetch from "node-fetch";
import FlexSearch from "flexsearch";

const ToolInputSchema = z.object({});

enum ToolName {
  GET_PROVIDERS = "getProviders",
  GET_SERVERS = "getServers",
  FIND_SERVERS = "findServers",
  FIND_TOOLS = "findTools",
  FIND_PROMPTS = "findPrompts",
  FIND_RESOURCES = "findResources",
  FIND_DEPLOYMENTS = "findDeployments",
}

enum PromptName {
  MCP_MANIFEST = "mcpManifest",
  MCP_SERVER_REGISTRATION = "mcpServerRegistration",
}

export const createServer = () => {
  const server = new Server(
    {
      name: "xRegistry-MCP-Server",
      version: "1.0.0",
    },
    {
      capabilities: {
        prompts: {},
        tools: {},
        logging: {},
      },
    }
  );



  const registryUrl = "https://clemensv.github.io/xregistry-mcp/";

  async function loadIndex(type: string) {
    // Load the pre-built index
    const indexData: Record<string, unknown> = await fetch(`${registryUrl}/${type}_index.flex.json`).then(r => r.json()) as Record<string, unknown>;

    // Create the index with storage enabled
    const index = new FlexSearch.Document({
      document: {
        id: 'id',
        index: ['name', 'description'],
        store: true
      }
    });

    // Import the index
    for (const [key, value] of Object.entries(indexData)) {
      await index.import(key, value);
    }

    return index;
  }

  const flexIndexes: {
    server: FlexSearch.Document<unknown, true>
    tool: FlexSearch.Document<unknown, true>
    resource: FlexSearch.Document<unknown, true>
    prompt: FlexSearch.Document<unknown, true>
  } = {
    server: null as any,
    tool: null as any,
    resource: null as any,
    prompt: null as any,
  };

  const loadIndexes = async () => {
    flexIndexes.server = await loadIndex("servers");
    flexIndexes.tool = await loadIndex("tools");
    flexIndexes.resource = await loadIndex("resources");
    flexIndexes.prompt = await loadIndex("prompts");
  };

  loadIndexes().catch(console.error);

  const fetchRegistryData = async (path: string) => {
    const response = await fetch(`${registryUrl}${path}`);
    if (!response.ok) {
      throw new Error(`Failed to fetch data from ${path}`);
    }
    return await response.json();
  };

  server.setRequestHandler(ListToolsRequestSchema, async () => {
    return {
      tools: [
        {
          name: ToolName.GET_PROVIDERS,
          description: "Retrieve all MCP providers.",
          inputSchema: {},
        },
        {
          name: ToolName.GET_SERVERS,
          description: "Retrieve all servers for a given provider.",
          inputSchema: { type: "object", properties: { providerId: { type: "string" } }, required: ["providerId"] },
        },
        {
          name: ToolName.FIND_SERVERS,
          description: "Search for servers using keywords.",
          inputSchema: { type: "object", properties: { query: { type: "string" } }, required: ["query"] },
        },
        {
          name: ToolName.FIND_TOOLS,
          description: "Search for tools using keywords.",
          inputSchema: { type: "object", properties: { query: { type: "string" } }, required: ["query"] },
        },
        {
          name: ToolName.FIND_PROMPTS,
          description: "Search for prompts using keywords.",
          inputSchema: { type: "object", properties: { query: { type: "string" } }, required: ["query"] },
        },
        {
          name: ToolName.FIND_RESOURCES,
          description: "Search for resources using keywords.",
          inputSchema: { type: "object", properties: { query: { type: "string" } }, required: ["query"] },
        },
        {
          name: ToolName.FIND_DEPLOYMENTS,
          description: "Search for deployments using keywords.",
          inputSchema: { type: "object", properties: { query: { type: "string" } }, required: ["query"] },
        },
      ],
    };
  });

  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args } = request.params;

    if (name === ToolName.GET_PROVIDERS) {
      return { content: [{ type: "json", data: await fetchRegistryData("mcpproviders") }] };
    }

    if (name === ToolName.GET_SERVERS) {
      const { providerId } = args as { providerId: string };
      return { content: [{ type: "json", data: await fetchRegistryData(`mcpproviders/${providerId}/servers`) }] };
    }

    if (name === ToolName.FIND_SERVERS) {
      const { query } = args as { query: string };
      const results = flexIndexes.server.search(String(query), 10);
      return { content: [{ type: "json", data: results }] };
    }

    if (name === ToolName.FIND_TOOLS) {
      const { query } = args as { query: string };
      const results = flexIndexes.tool.search(String(query), 10);
      return { content: [{ type: "json", data: results }] };
    }

    if (name === ToolName.FIND_PROMPTS) {
      const { query } = args as { query: string };
      const results = flexIndexes.prompt.search(String(query), 10);
      return { content: [{ type: "json", data: results }] };
    }

    if (name === ToolName.FIND_RESOURCES) {
      const { query } = args as { query: string };
      const results = flexIndexes.resource.search(String(query), 10);
      return { content: [{ type: "json", data: results }] };
    }

    if (name === ToolName.FIND_DEPLOYMENTS) {
      const { query } = args as { query: string };
      const results = flexIndexes.server.search(String(query), 10); // Assuming deployments are part of servers
      return { content: [{ type: "json", data: results }] };
    }

    throw new Error(`Unknown tool: ${name}`);
  });

  server.setRequestHandler(ListPromptsRequestSchema, async () => {
    return {
      prompts: [
        {
          name: PromptName.MCP_MANIFEST,
          description: "Retrieve the MCP manifest.",
        },
        {
          name: PromptName.MCP_SERVER_REGISTRATION,
          description: "Register a new MCP server.",
        },
      ],
    };
  });

  const cleanup = () => {
    // Add cleanup logic here, such as closing connections or clearing resources
    console.log('Cleaning up resources...');
  };

  return { server, cleanup };
};
