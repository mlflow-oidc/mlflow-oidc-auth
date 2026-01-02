import type { ExperimentPermission } from "../../shared/types/entity";
import { fetchUserExperimentPermissions } from "../services/entity-service";
import { useApi } from "./use-api";
import { useCallback } from "react";

interface UseUserExperimentPermissionsProps {
  username: string | null;
}

export function useUserExperimentPermissions({
  username,
}: UseUserExperimentPermissionsProps) {
  const fetcher = useCallback(
    (signal?: AbortSignal) => {
      if (username === null) {
        return Promise.resolve([]) as Promise<ExperimentPermission[]>;
      }
      return fetchUserExperimentPermissions(username, signal);
    },
    [username]
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
