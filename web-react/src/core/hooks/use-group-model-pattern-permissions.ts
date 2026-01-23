import type { ModelPatternPermission } from "../../shared/types/entity";
import { fetchGroupModelPatternPermissions } from "../services/entity-service";
import { useApi } from "./use-api";
import { useCallback } from "react";

interface UseGroupModelPatternPermissionsProps {
  groupName: string | null;
}

export function useGroupModelPatternPermissions({
  groupName,
}: UseGroupModelPatternPermissionsProps) {
  const fetcher = useCallback(
    (signal?: AbortSignal) => {
      if (groupName === null) {
        return Promise.resolve([]) as Promise<ModelPatternPermission[]>;
      }
      return fetchGroupModelPatternPermissions(groupName, signal);
    },
    [groupName]
  );

  const {
    data,
    isLoading,
    error,
    refetch: refresh,
  } = useApi<ModelPatternPermission[]>(fetcher);

  return {
    permissions: data ?? [],
    isLoading,
    error,
    refresh,
  };
}
