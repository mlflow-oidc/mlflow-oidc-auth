import type { BasePatternPermission } from "../../shared/types/entity";
import { fetchUserGatewayModelPatternPermissions } from "../services/gateway-service";
import { useApi } from "./use-api";
import { useCallback } from "react";

interface UseUserGatewayModelPatternPermissionsProps {
  username: string | null;
}

export function useUserGatewayModelPatternPermissions({
  username,
}: UseUserGatewayModelPatternPermissionsProps) {
  const fetcher = useCallback(
    (signal?: AbortSignal) => {
      if (username === null) {
        return Promise.resolve([]) as Promise<BasePatternPermission[]>;
      }
      return fetchUserGatewayModelPatternPermissions(username, signal);
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
