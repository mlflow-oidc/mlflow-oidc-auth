import type { EntityPermission } from "../../shared/types/entity";
import { fetchExperimentUserPermissions } from "../services/entity-service";
import { useApi } from "./use-api";
import { useCallback } from "react";

interface UseExperimentUserPermissionsProps {
  experimentId: string | null;
}

export function useExperimentUserPermissions({
  experimentId,
}: UseExperimentUserPermissionsProps) {
  const fetcher = useCallback(
    (signal?: AbortSignal) => {
      if (experimentId === null) {
        return Promise.resolve([]) as Promise<EntityPermission[]>;
      }
      return fetchExperimentUserPermissions(experimentId, signal);
    },
    [experimentId],
  );

  const {
    data,
    isLoading,
    error,
    refetch: refresh,
  } = useApi<EntityPermission[]>(fetcher);

  return {
    experimentUserPermissions: data ?? [],
    isLoading,
    error,
    refresh,
  };
}
