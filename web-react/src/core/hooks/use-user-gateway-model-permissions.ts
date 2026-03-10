import type { EntityPermission } from "../../shared/types/entity";
import { fetchUserGatewayModelPermissions } from "../services/gateway-service";
import { useApi } from "./use-api";
import { useCallback } from "react";

interface UseUserGatewayModelPermissionsProps {
  username: string | null;
}

export function useUserGatewayModelPermissions({
  username,
}: UseUserGatewayModelPermissionsProps) {
  const fetcher = useCallback(
    (signal?: AbortSignal) => {
      if (username === null) {
        return Promise.resolve([]) as Promise<EntityPermission[]>;
      }
      return fetchUserGatewayModelPermissions(username, signal);
    },
    [username],
  );

  const {
    data,
    isLoading,
    error,
    refetch: refresh,
  } = useApi<EntityPermission[]>(fetcher);

  return {
    permissions: data ?? [],
    isLoading,
    error,
    refresh,
  };
}
