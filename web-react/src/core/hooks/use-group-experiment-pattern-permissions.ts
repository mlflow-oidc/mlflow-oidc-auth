import type { ExperimentPatternPermission } from "../../shared/types/entity";
import { fetchGroupExperimentPatternPermissions } from "../services/entity-service";
import { useApi } from "./use-api";
import { useCallback } from "react";

interface UseGroupExperimentPatternPermissionsProps {
  groupName: string | null;
}

export function useGroupExperimentPatternPermissions({
  groupName,
}: UseGroupExperimentPatternPermissionsProps) {
  const fetcher = useCallback(
    (signal?: AbortSignal) => {
      if (groupName === null) {
        return Promise.resolve([]) as Promise<ExperimentPatternPermission[]>;
      }
      return fetchGroupExperimentPatternPermissions(groupName, signal);
    },
    [groupName]
  );

  const {
    data,
    isLoading,
    error,
    refetch: refresh,
  } = useApi<ExperimentPatternPermission[]>(fetcher);

  return {
    permissions: data ?? [],
    isLoading,
    error,
    refresh,
  };
}
