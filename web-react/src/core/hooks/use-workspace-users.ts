import type { WorkspaceUserPermission } from "../../shared/types/entity";
import { fetchWorkspaceUsers } from "../services/workspace-service";
import { useApi } from "./use-api";
import { useCallback } from "react";

interface UseWorkspaceUsersProps {
  workspace: string | undefined;
}

export function useWorkspaceUsers({ workspace }: UseWorkspaceUsersProps) {
  const fetcher = useCallback(
    (signal?: AbortSignal) => {
      if (!workspace) {
        return Promise.resolve([]) as Promise<WorkspaceUserPermission[]>;
      }
      return fetchWorkspaceUsers(workspace, signal);
    },
    [workspace],
  );

  const {
    data,
    isLoading,
    error,
    refetch: refresh,
  } = useApi<WorkspaceUserPermission[]>(fetcher);

  return {
    workspaceUsers: data ?? [],
    isLoading,
    error,
    refresh,
  };
}
