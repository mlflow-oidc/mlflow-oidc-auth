import type { EntityPermission } from "../../shared/types/entity";
import { fetchGroupGatewayEndpointPermissions } from "../services/gateway-service";
import { useApi } from "./use-api";
import { useCallback } from "react";

interface UseGroupGatewayEndpointPermissionsProps {
  groupName: string | null;
}

export function useGroupGatewayEndpointPermissions({
  groupName,
}: UseGroupGatewayEndpointPermissionsProps) {
  const fetcher = useCallback(
    (signal?: AbortSignal) => {
      if (groupName === null) {
        return Promise.resolve([]) as Promise<EntityPermission[]>;
      }
      return fetchGroupGatewayEndpointPermissions(groupName, signal);
    },
    [groupName],
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
