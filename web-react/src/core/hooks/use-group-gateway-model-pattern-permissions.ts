import type { BasePatternPermission } from "../../shared/types/entity";
import { fetchGroupGatewayModelPatternPermissions } from "../services/gateway-service";
import { useApi } from "./use-api";
import { useCallback } from "react";

interface UseGroupGatewayModelPatternPermissionsProps {
  groupName: string | null;
}

export function useGroupGatewayModelPatternPermissions({
  groupName,
}: UseGroupGatewayModelPatternPermissionsProps) {
  const fetcher = useCallback(
    (signal?: AbortSignal) => {
      if (groupName === null) {
        return Promise.resolve([]) as Promise<BasePatternPermission[]>;
      }
      return fetchGroupGatewayModelPatternPermissions(groupName, signal);
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
