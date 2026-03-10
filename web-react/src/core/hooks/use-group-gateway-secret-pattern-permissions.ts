import type { BasePatternPermission } from "../../shared/types/entity";
import { fetchGroupGatewaySecretPatternPermissions } from "../services/gateway-service";
import { useApi } from "./use-api";
import { useCallback } from "react";

interface UseGroupGatewaySecretPatternPermissionsProps {
  groupName: string | null;
}

export function useGroupGatewaySecretPatternPermissions({
  groupName,
}: UseGroupGatewaySecretPatternPermissionsProps) {
  const fetcher = useCallback(
    (signal?: AbortSignal) => {
      if (groupName === null) {
        return Promise.resolve([]) as Promise<BasePatternPermission[]>;
      }
      return fetchGroupGatewaySecretPatternPermissions(groupName, signal);
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
