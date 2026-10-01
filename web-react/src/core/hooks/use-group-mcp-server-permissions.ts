import type { EntityPermission } from "../../shared/types/entity";
import { fetchGroupMcpServerPermissions } from "../services/mcp-server-service";
import { useApi } from "./use-api";
import { useCallback } from "react";

interface UseGroupMcpServerPermissionsProps {
  groupName: string | null;
}

export function useGroupMcpServerPermissions({
  groupName,
}: UseGroupMcpServerPermissionsProps) {
  const fetcher = useCallback(
    (signal?: AbortSignal) => {
      if (groupName === null) {
        return Promise.resolve([]) as Promise<EntityPermission[]>;
      }
      return fetchGroupMcpServerPermissions(groupName, signal);
    },
    [groupName],
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
