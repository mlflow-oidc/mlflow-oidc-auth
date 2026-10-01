import type { EntityPermission } from "../../shared/types/entity";
import { fetchMcpServerGroupPermissions } from "../services/mcp-server-service";
import { useApi } from "./use-api";
import { useCallback } from "react";

interface UseMcpServerGroupPermissionsProps {
  name: string | null;
}

export function useMcpServerGroupPermissions({
  name,
}: UseMcpServerGroupPermissionsProps) {
  const fetcher = useCallback(
    (signal?: AbortSignal) => {
      if (name === null) {
        return Promise.resolve([]) as Promise<EntityPermission[]>;
      }
      return fetchMcpServerGroupPermissions(name, signal);
    },
    [name],
  );

  const {
    data,
    isLoading,
    error,
    refetch: refresh,
  } = useApi<EntityPermission[]>(fetcher);

  return {
    permissions: data ?? [],
    isLoading,
    error,
    refresh,
  };
}
