import type { PromptPatternPermission } from "../../shared/types/entity";
import { fetchGroupPromptPatternPermissions } from "../services/entity-service";
import { useApi } from "./use-api";
import { useCallback } from "react";

interface UseGroupPromptPatternPermissionsProps {
  groupName: string | null;
}

export function useGroupPromptPatternPermissions({
  groupName,
}: UseGroupPromptPatternPermissionsProps) {
  const fetcher = useCallback(
    (signal?: AbortSignal) => {
      if (groupName === null) {
        return Promise.resolve([]) as Promise<PromptPatternPermission[]>;
      }
      return fetchGroupPromptPatternPermissions(groupName, signal);
    },
    [groupName],
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
