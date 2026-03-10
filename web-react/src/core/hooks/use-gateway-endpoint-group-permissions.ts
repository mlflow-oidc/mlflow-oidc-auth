import type { EntityPermission } from "../../shared/types/entity";
import { fetchGatewayEndpointGroupPermissions } from "../services/gateway-service";
import { useApi } from "./use-api";
import { useCallback } from "react";

interface UseGatewayEndpointGroupPermissionsProps {
  name: string | null;
}

export function useGatewayEndpointGroupPermissions({
  name,
}: UseGatewayEndpointGroupPermissionsProps) {
  const fetcher = useCallback(
    (signal?: AbortSignal) => {
      if (name === null) {
        return Promise.resolve([]) as Promise<EntityPermission[]>;
      }
      return fetchGatewayEndpointGroupPermissions(name, signal);
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
