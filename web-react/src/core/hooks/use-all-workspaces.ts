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

type LoadedMemberCounts = {
  source: WorkspaceListItem[];
  counts: Record<string, WorkspaceMemberCounts>;
};

export function useAllWorkspaces() {
  const {
    data,
    isLoading,
    error,
    refetch: refresh,
  } = useApi<WorkspaceListResponse>(fetchAllWorkspaces);
  const allWorkspaces: WorkspaceListItem[] | null = data?.workspaces ?? null;

  const [loaded, setLoaded] = useState<LoadedMemberCounts | null>(null);

  useEffect(() => {
    if (!allWorkspaces?.length) {
      return;
    }
    const controller = new AbortController();
    const source = allWorkspaces;

    const load = async () => {
      try {
        const results = await Promise.all(
          source.map(async (ws) => {
            const counts = await fetchWorkspaceMemberCounts(
              ws.name,
              controller.signal,
            );
            return [ws.name, counts] as const;
          }),
        );
        if (!controller.signal.aborted) {
          setLoaded({ source, counts: Object.fromEntries(results) });
        }
      } catch {
        /* ignore abort/fetch errors: memberCounts simply stays unresolved */
      }
    };

    void load();
    return () => controller.abort();
  }, [allWorkspaces]);

  // Counts are only valid for the workspace list they were fetched for, kept
  // by reference rather than reset via an effect. This means switching lists
  // — including empty -> non-empty with a reused name, or a slow fetch being
  // superseded by a newer one — never shows a previous list's stale counts,
  // not even for one render.
  const memberCounts =
    loaded && loaded.source === allWorkspaces ? loaded.counts : null;

  return { allWorkspaces, memberCounts, isLoading, error, refresh };
}
