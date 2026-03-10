import type { EntityPermission } from "../../shared/types/entity";
import { fetchGroupGatewaySecretPermissions } from "../services/gateway-service";
import { useApi } from "./use-api";
import { useCallback } from "react";

interface UseGroupGatewaySecretPermissionsProps {
  groupName: string | null;
}

export function useGroupGatewaySecretPermissions({
  groupName,
}: UseGroupGatewaySecretPermissionsProps) {
  const fetcher = useCallback(
    (signal?: AbortSignal) => {
      if (groupName === null) {
        return Promise.resolve([]) as Promise<EntityPermission[]>;
      }
      return fetchGroupGatewaySecretPermissions(groupName, signal);
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
