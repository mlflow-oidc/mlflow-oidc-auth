import type { EntityPermission } from "../../shared/types/entity";
import { fetchExperimentGroupPermissions } from "../services/entity-service";
import { useApi } from "./use-api";
import { useCallback } from "react";

interface UseExperimentGroupPermissionsProps {
  experimentId: string | null;
}

export function useExperimentGroupPermissions({
  experimentId,
}: UseExperimentGroupPermissionsProps) {
  const fetcher = useCallback(
    (signal?: AbortSignal) => {
      if (experimentId === null) {
        return Promise.resolve([]) as Promise<EntityPermission[]>;
      }
      return fetchExperimentGroupPermissions(experimentId, signal);
    },
    [experimentId]
  );

  const {
    data,
    isLoading,
    error,
    refetch: refresh,
  } = useApi<EntityPermission[]>(fetcher);

  return {
    experimentGroupPermissions: data ?? [],
    isLoading,
    error,
    refresh,
  };
}
