import type { BasePatternPermission } from "../../shared/types/entity";
import { fetchGroupGatewayEndpointPatternPermissions } from "../services/gateway-service";
import { useApi } from "./use-api";
import { useCallback } from "react";

interface UseGroupGatewayEndpointPatternPermissionsProps {
  groupName: string | null;
}

export function useGroupGatewayEndpointPatternPermissions({
  groupName,
}: UseGroupGatewayEndpointPatternPermissionsProps) {
  const fetcher = useCallback(
    (signal?: AbortSignal) => {
      if (groupName === null) {
        return Promise.resolve([]) as Promise<BasePatternPermission[]>;
      }
      return fetchGroupGatewayEndpointPatternPermissions(groupName, signal);
    },
    [groupName],
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
