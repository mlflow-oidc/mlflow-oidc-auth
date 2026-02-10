import type { ModelPatternPermission } from "../../shared/types/entity";
import { fetchUserModelPatternPermissions } from "../services/entity-service";
import { useApi } from "./use-api";
import { useCallback } from "react";

interface UseUserModelPatternPermissionsProps {
  username: string | null;
}

export function useUserModelPatternPermissions({
  username,
}: UseUserModelPatternPermissionsProps) {
  const fetcher = useCallback(
    (signal?: AbortSignal) => {
      if (username === null) {
        return Promise.resolve([]) as Promise<ModelPatternPermission[]>;
      }
      return fetchUserModelPatternPermissions(username, signal);
    },
    [username],
  );

  const {
    data,
    isLoading,
    error,
    refetch: refresh,
  } = useApi<ModelPatternPermission[]>(fetcher);

  return {
    permissions: data ?? [],
    isLoading,
    error,
    refresh,
  };
}
