import type { PromptPatternPermission } from "../../shared/types/entity";
import { fetchUserPromptPatternPermissions } from "../services/entity-service";
import { useApi } from "./use-api";
import { useCallback } from "react";

interface UseUserPromptPatternPermissionsProps {
  username: string | null;
}

export function useUserPromptPatternPermissions({
  username,
}: UseUserPromptPatternPermissionsProps) {
  const fetcher = useCallback(
    (signal?: AbortSignal) => {
      if (username === null) {
        return Promise.resolve([]) as Promise<PromptPatternPermission[]>;
      }
      return fetchUserPromptPatternPermissions(username, signal);
    },
    [username]
  );

  const {
    data,
    isLoading,
    error,
    refetch: refresh,
  } = useApi<PromptPatternPermission[]>(fetcher);

  return {
    permissions: data ?? [],
    isLoading,
    error,
    refresh,
  };
}
