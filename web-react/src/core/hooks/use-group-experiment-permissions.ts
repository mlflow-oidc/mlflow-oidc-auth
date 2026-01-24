import type { ExperimentPermission } from "../../shared/types/entity";
import { fetchGroupExperimentPermissions } from "../services/entity-service";
import { useApi } from "./use-api";
import { useCallback } from "react";

interface UseGroupExperimentPermissionsProps {
  groupName: string | null;
}

export function useGroupExperimentPermissions({
  groupName,
}: UseGroupExperimentPermissionsProps) {
  const fetcher = useCallback(
    (signal?: AbortSignal) => {
      if (groupName === null) {
        return Promise.resolve([]) as Promise<ExperimentPermission[]>;
      }
      return fetchGroupExperimentPermissions(groupName, signal);
    },
    [groupName],
  );

  const {
    data,
    isLoading,
    error,
    refetch: refresh,
  } = useApi<ExperimentPermission[]>(fetcher);

  return {
    permissions: data ?? [],
    isLoading,
    error,
    refresh,
  };
}
