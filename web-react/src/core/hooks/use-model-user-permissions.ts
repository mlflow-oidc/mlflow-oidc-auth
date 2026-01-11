import type { EntityPermission } from "../../shared/types/entity";
import { fetchModelUserPermissions } from "../services/entity-service";
import { useApi } from "./use-api";
import { useCallback } from "react";

interface UseModelUserPermissionsProps {
  modelName: string | null;
}

export function useModelUserPermissions({
  modelName,
}: UseModelUserPermissionsProps) {
  const fetcher = useCallback(
    (signal?: AbortSignal) => {
      if (modelName === null) {
        return Promise.resolve([]) as Promise<EntityPermission[]>;
      }
      return fetchModelUserPermissions(modelName, signal);
    },
    [modelName]
  );

  const {
    data,
    isLoading,
    error,
    refetch: refresh,
  } = useApi<EntityPermission[]>(fetcher);

  return {
    modelUserPermissions: data ?? [],
    isLoading,
    error,
    refresh,
  };
}
