import type { ModelPermission } from "../../shared/types/entity";
import { fetchGroupRegisteredModelPermissions } from "../services/entity-service";
import { useApi } from "./use-api";
import { useCallback } from "react";

interface UseGroupRegisteredModelPermissionsProps {
  groupName: string | null;
}

export function useGroupRegisteredModelPermissions({
  groupName,
}: UseGroupRegisteredModelPermissionsProps) {
  const fetcher = useCallback(
    (signal?: AbortSignal) => {
      if (groupName === null) {
        return Promise.resolve([]) as Promise<ModelPermission[]>;
      }
      return fetchGroupRegisteredModelPermissions(groupName, signal);
    },
    [groupName]
  );

  const {
    data,
    isLoading,
    error,
    refetch: refresh,
  } = useApi<ModelPermission[]>(fetcher);

  return {
    permissions: data ?? [],
    isLoading,
    error,
    refresh,
  };
}
