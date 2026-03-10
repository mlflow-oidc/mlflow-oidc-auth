import type { EntityPermission } from "../../shared/types/entity";
import { fetchUserGatewaySecretPermissions } from "../services/gateway-service";
import { useApi } from "./use-api";
import { useCallback } from "react";

interface UseUserGatewaySecretPermissionsProps {
  username: string | null;
}

export function useUserGatewaySecretPermissions({
  username,
}: UseUserGatewaySecretPermissionsProps) {
  const fetcher = useCallback(
    (signal?: AbortSignal) => {
      if (username === null) {
        return Promise.resolve([]) as Promise<EntityPermission[]>;
      }
      return fetchUserGatewaySecretPermissions(username, signal);
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
