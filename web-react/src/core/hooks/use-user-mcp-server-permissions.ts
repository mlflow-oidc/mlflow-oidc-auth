import type { EntityPermission } from "../../shared/types/entity";
import { fetchUserMcpServerPermissions } from "../services/mcp-server-service";
import { useApi } from "./use-api";
import { useCallback } from "react";

interface UseUserMcpServerPermissionsProps {
  username: string | null;
}

export function useUserMcpServerPermissions({
  username,
}: UseUserMcpServerPermissionsProps) {
  const fetcher = useCallback(
    (signal?: AbortSignal) => {
      if (username === null) {
        return Promise.resolve([]) as Promise<EntityPermission[]>;
      }
      return fetchUserMcpServerPermissions(username, signal);
    },
    [username],
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
