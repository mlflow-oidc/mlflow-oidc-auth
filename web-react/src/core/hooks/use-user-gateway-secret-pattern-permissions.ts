import type { BasePatternPermission } from "../../shared/types/entity";
import { fetchUserGatewaySecretPatternPermissions } from "../services/gateway-service";
import { useApi } from "./use-api";
import { useCallback } from "react";

interface UseUserGatewaySecretPatternPermissionsProps {
  username: string | null;
}

export function useUserGatewaySecretPatternPermissions({
  username,
}: UseUserGatewaySecretPatternPermissionsProps) {
  const fetcher = useCallback(
    (signal?: AbortSignal) => {
      if (username === null) {
        return Promise.resolve([]) as Promise<BasePatternPermission[]>;
      }
      return fetchUserGatewaySecretPatternPermissions(username, signal);
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
