import type { EntityPermission } from "../../shared/types/entity";
import { fetchGatewayModelGroupPermissions } from "../services/gateway-service";
import { useApi } from "./use-api";
import { useCallback } from "react";

interface UseGatewayModelGroupPermissionsProps {
  name: string | null;
}

export function useGatewayModelGroupPermissions({
  name,
}: UseGatewayModelGroupPermissionsProps) {
  const fetcher = useCallback(
    (signal?: AbortSignal) => {
      if (name === null) {
        return Promise.resolve([]) as Promise<EntityPermission[]>;
      }
      return fetchGatewayModelGroupPermissions(name, signal);
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
