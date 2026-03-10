import type { EntityPermission } from "../../shared/types/entity";
import { fetchGatewaySecretUserPermissions } from "../services/gateway-service";
import { useApi } from "./use-api";
import { useCallback } from "react";

interface UseGatewaySecretUserPermissionsProps {
  name: string | null;
}

export function useGatewaySecretUserPermissions({
  name,
}: UseGatewaySecretUserPermissionsProps) {
  const fetcher = useCallback(
    (signal?: AbortSignal) => {
      if (name === null) {
        return Promise.resolve([]) as Promise<EntityPermission[]>;
      }
      return fetchGatewaySecretUserPermissions(name, signal);
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
