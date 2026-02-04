import type { EntityPermission } from "../../shared/types/entity";
import { fetchGatewayEndpointUserPermissions } from "../services/gateway-service";
import { useApi } from "./use-api";
import { useCallback } from "react";

interface UseGatewayEndpointUserPermissionsProps {
  name: string | null;
}

export function useGatewayEndpointUserPermissions({
  name,
}: UseGatewayEndpointUserPermissionsProps) {
  const fetcher = useCallback(
    (signal?: AbortSignal) => {
      if (name === null) {
        return Promise.resolve([]) as Promise<EntityPermission[]>;
      }
      return fetchGatewayEndpointUserPermissions(name, signal);
    },
    [name],
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
