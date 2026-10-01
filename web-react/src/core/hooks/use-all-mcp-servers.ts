import { fetchAllMcpServers } from "../services/mcp-server-service";
import type { McpServerListItem } from "../../shared/types/entity";
import { useApi } from "./use-api";

export function useAllMcpServers() {
  const {
    data: allMcpServers,
    isLoading,
    error,
    refetch: refresh,
  } = useApi<McpServerListItem[]>(fetchAllMcpServers);

  return { allMcpServers, isLoading, error, refresh };
}
