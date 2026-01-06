import type { EntityPermission } from "../../shared/types/entity";
import { fetchModelGroupPermissions } from "../services/entity-service";
import { useApi } from "./use-api";
import { useCallback } from "react";

interface UseModelGroupPermissionsProps {
  modelName: string | null;
}

export function useModelGroupPermissions({
  modelName,
}: UseModelGroupPermissionsProps) {
  const fetcher = useCallback(
    (signal?: AbortSignal) => {
      if (modelName === null) {
        return Promise.resolve([]) as Promise<EntityPermission[]>;
      }
      return fetchModelGroupPermissions(modelName, signal);
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
    modelGroupPermissions: data ?? [],
    isLoading,
    error,
    refresh,
  };
}
