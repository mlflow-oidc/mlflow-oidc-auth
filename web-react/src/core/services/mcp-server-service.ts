import {
  createDynamicApiFetcher,
  createStaticApiFetcher,
} from "./create-api-fetcher.ts";
import { createPagedFetcher } from "./paged-list";
import { STATIC_API_ENDPOINTS } from "../configs/api-endpoints";
import type {
  EntityPermission,
  McpServerListItem,
} from "../../shared/types/entity";

// Every MCP server the caller may manage, unpaginated (grant pickers)
export const fetchAllMcpServers = createStaticApiFetcher<McpServerListItem[]>({
  endpointKey: "ALL_MCP_SERVERS",
  responseType: [] as McpServerListItem[],
});

// MCP servers of the request's workspace the caller may manage (all of them for an admin).
export const fetchMcpServersPage = createPagedFetcher<
  McpServerListItem[],
  McpServerListItem
>(STATIC_API_ENDPOINTS.ALL_MCP_SERVERS, {
  extract: (body) => body ?? [],
  displayKey: (server) => server.name,
});

// Users and groups holding a grant on one server
export const fetchMcpServerUserPermissions = createDynamicApiFetcher<
  EntityPermission[],
  "MCP_SERVER_USER_PERMISSIONS"
>({
  endpointKey: "MCP_SERVER_USER_PERMISSIONS",
  responseType: [] as EntityPermission[],
});

export const fetchMcpServerGroupPermissions = createDynamicApiFetcher<
  EntityPermission[],
  "MCP_SERVER_GROUP_PERMISSIONS"
>({
  endpointKey: "MCP_SERVER_GROUP_PERMISSIONS",
  responseType: [] as EntityPermission[],
});

// A user's / a group's MCP server permissions (there is no pattern API for MCP servers)
export const fetchUserMcpServerPermissions = createDynamicApiFetcher<
  EntityPermission[],
  "USER_MCP_SERVER_PERMISSIONS"
>({
  endpointKey: "USER_MCP_SERVER_PERMISSIONS",
  responseType: [] as EntityPermission[],
});

export const fetchGroupMcpServerPermissions = createDynamicApiFetcher<
  EntityPermission[],
  "GROUP_MCP_SERVER_PERMISSIONS"
>({
  endpointKey: "GROUP_MCP_SERVER_PERMISSIONS",
  responseType: [] as EntityPermission[],
});
