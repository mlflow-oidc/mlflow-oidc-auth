import type { ModelPermission } from "../../shared/types/entity";
import { fetchUserRegisteredModelPermissions } from "../services/entity-service";
import { useApi } from "./use-api";
import { useCallback } from "react";

interface UseUserRegisteredModelPermissionsProps {
  username: string | null;
}

export function useUserRegisteredModelPermissions({
  username,
}: UseUserRegisteredModelPermissionsProps) {
  const fetcher = useCallback(
    (signal?: AbortSignal) => {
      if (username === null) {
        return Promise.resolve([]) as Promise<ModelPermission[]>;
      }
      return fetchUserRegisteredModelPermissions(username, signal);
    },
    [username]
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
