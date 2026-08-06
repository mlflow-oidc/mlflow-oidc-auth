import type { WorkspaceGroupPermission } from "../../shared/types/entity";
import { fetchWorkspaceGroups } from "../services/workspace-service";
import { useApi } from "./use-api";
import { useCallback } from "react";

interface UseWorkspaceGroupsProps {
  workspace: string | undefined;
}

export function useWorkspaceGroups({ workspace }: UseWorkspaceGroupsProps) {
  const fetcher = useCallback(
    (signal?: AbortSignal) => {
      if (!workspace) {
        return Promise.resolve([]) as Promise<WorkspaceGroupPermission[]>;
      }
      return fetchWorkspaceGroups(workspace, signal);
    },
    [workspace],
  );

  const {
    data,
    isLoading,
    error,
    refetch: refresh,
  } = useApi<WorkspaceGroupPermission[]>(fetcher);

  return {
    workspaceGroups: data ?? [],
    isLoading,
    error,
    refresh,
  };
}
