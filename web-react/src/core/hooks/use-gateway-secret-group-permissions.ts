import type { EntityPermission } from "../../shared/types/entity";
import { fetchGatewaySecretGroupPermissions } from "../services/gateway-service";
import { useApi } from "./use-api";
import { useCallback } from "react";

interface UseGatewaySecretGroupPermissionsProps {
  name: string | null;
}

export function useGatewaySecretGroupPermissions({
  name,
}: UseGatewaySecretGroupPermissionsProps) {
  const fetcher = useCallback(
    (signal?: AbortSignal) => {
      if (name === null) {
        return Promise.resolve([]) as Promise<EntityPermission[]>;
      }
      return fetchGatewaySecretGroupPermissions(name, signal);
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
