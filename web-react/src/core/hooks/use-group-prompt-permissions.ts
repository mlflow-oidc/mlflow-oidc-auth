import type { PromptPermission } from "../../shared/types/entity";
import { fetchGroupPromptPermissions } from "../services/entity-service";
import { useApi } from "./use-api";
import { useCallback } from "react";

interface UseGroupPromptPermissionsProps {
  groupName: string | null;
}

export function useGroupPromptPermissions({
  groupName,
}: UseGroupPromptPermissionsProps) {
  const fetcher = useCallback(
    (signal?: AbortSignal) => {
      if (groupName === null) {
        return Promise.resolve([]) as Promise<PromptPermission[]>;
      }
      return fetchGroupPromptPermissions(groupName, signal);
    },
    [groupName]
  );

  const {
    data,
    isLoading,
    error,
    refetch: refresh,
  } = useApi<PromptPermission[]>(fetcher);

  return {
    permissions: data ?? [],
    isLoading,
    error,
    refresh,
  };
}
