import type { EntityPermission } from "../../shared/types/entity";
import { fetchUserGatewayEndpointPermissions } from "../services/gateway-service";
import { useApi } from "./use-api";
import { useCallback } from "react";

interface UseUserGatewayEndpointPermissionsProps {
  username: string | null;
}

export function useUserGatewayEndpointPermissions({
  username,
}: UseUserGatewayEndpointPermissionsProps) {
  const fetcher = useCallback(
    (signal?: AbortSignal) => {
      if (username === null) {
        return Promise.resolve([]) as Promise<EntityPermission[]>;
      }
      return fetchUserGatewayEndpointPermissions(username, signal);
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
