import { useState, useEffect } from "react";
import type {
  WorkspaceListItem,
  WorkspaceListResponse,
  WorkspaceMemberCounts,
} from "../../shared/types/entity";
import {
  fetchAllWorkspaces,
  fetchWorkspaceMemberCounts,
} from "../services/workspace-service";
import { useApi } from "./use-api";

export function useAllWorkspaces() {
  const {
    data,
    isLoading,
    error,
    refetch: refresh,
  } = useApi<WorkspaceListResponse>(fetchAllWorkspaces);
  const allWorkspaces: WorkspaceListItem[] | null =
    data?.workspaces ?? null;

  const [memberCounts, setMemberCounts] = useState<Record<
    string,
    WorkspaceMemberCounts
  > | null>(null);

  useEffect(() => {
    if (!allWorkspaces?.length) {
      setMemberCounts(null);
      return;
    }
    const controller = new AbortController();
    Promise.all(
      allWorkspaces.map(async (ws) => {
        const counts = await fetchWorkspaceMemberCounts(
          ws.name,
          controller.signal,
        );
        return [ws.name, counts] as const;
      }),
    )
      .then((results) => {
        if (!controller.signal.aborted) {
          setMemberCounts(Object.fromEntries(results));
        }
      })
      .catch(() => {
        /* ignore abort errors */
      });
    return () => controller.abort();
  }, [allWorkspaces]);

  return { allWorkspaces, memberCounts, isLoading, error, refresh };
}
