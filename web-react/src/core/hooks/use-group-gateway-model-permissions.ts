import type { EntityPermission } from "../../shared/types/entity";
import { fetchGroupGatewayModelPermissions } from "../services/gateway-service";
import { useApi } from "./use-api";
import { useCallback } from "react";

interface UseGroupGatewayModelPermissionsProps {
  groupName: string | null;
}

export function useGroupGatewayModelPermissions({
  groupName,
}: UseGroupGatewayModelPermissionsProps) {
  const fetcher = useCallback(
    (signal?: AbortSignal) => {
      if (groupName === null) {
        return Promise.resolve([]) as Promise<EntityPermission[]>;
      }
      return fetchGroupGatewayModelPermissions(groupName, signal);
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
