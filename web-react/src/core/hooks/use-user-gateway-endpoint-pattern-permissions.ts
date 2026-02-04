import type { BasePatternPermission } from "../../shared/types/entity";
import { fetchUserGatewayEndpointPatternPermissions } from "../services/gateway-service";
import { useApi } from "./use-api";
import { useCallback } from "react";

interface UseUserGatewayEndpointPatternPermissionsProps {
  username: string | null;
}

export function useUserGatewayEndpointPatternPermissions({
  username,
}: UseUserGatewayEndpointPatternPermissionsProps) {
  const fetcher = useCallback(
    (signal?: AbortSignal) => {
      if (username === null) {
        return Promise.resolve([]) as Promise<BasePatternPermission[]>;
      }
      return fetchUserGatewayEndpointPatternPermissions(username, signal);
    },
    [username],
  );

  const {
    data,
    isLoading,
    error,
    refetch: refresh,
  } = useApi<BasePatternPermission[]>(fetcher);

  return {
    permissions: data ?? [],
    isLoading,
    error,
    refresh,
  };
}
