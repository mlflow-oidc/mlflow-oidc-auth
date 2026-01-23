import type { ExperimentPatternPermission } from "../../shared/types/entity";
import { fetchUserExperimentPatternPermissions } from "../services/entity-service";
import { useApi } from "./use-api";
import { useCallback } from "react";

interface UseUserExperimentPatternPermissionsProps {
  username: string | null;
}

export function useUserExperimentPatternPermissions({
  username,
}: UseUserExperimentPatternPermissionsProps) {
  const fetcher = useCallback(
    (signal?: AbortSignal) => {
      if (username === null) {
        return Promise.resolve([]) as Promise<ExperimentPatternPermission[]>;
      }
      return fetchUserExperimentPatternPermissions(username, signal);
    },
    [username]
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
