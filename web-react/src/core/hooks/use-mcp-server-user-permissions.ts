import type { EntityPermission } from "../../shared/types/entity";
import { fetchMcpServerUserPermissions } from "../services/mcp-server-service";
import { useApi } from "./use-api";
import { useCallback } from "react";

interface UseMcpServerUserPermissionsProps {
  name: string | null;
}

export function useMcpServerUserPermissions({
  name,
}: UseMcpServerUserPermissionsProps) {
  const fetcher = useCallback(
    (signal?: AbortSignal) => {
      if (name === null) {
        return Promise.resolve([]) as Promise<EntityPermission[]>;
      }
      return fetchMcpServerUserPermissions(name, signal);
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
