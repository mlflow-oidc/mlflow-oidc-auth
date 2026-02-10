import type { EntityPermission } from "../../shared/types/entity";
import { fetchPromptUserPermissions } from "../services/entity-service";
import { useApi } from "./use-api";
import { useCallback } from "react";

interface UsePromptUserPermissionsProps {
  promptName: string | null;
}

export function usePromptUserPermissions({
  promptName,
}: UsePromptUserPermissionsProps) {
  const fetcher = useCallback(
    (signal?: AbortSignal) => {
      if (promptName === null) {
        return Promise.resolve([]) as Promise<EntityPermission[]>;
      }
      return fetchPromptUserPermissions(promptName, signal);
    },
    [promptName],
  );

  const {
    data,
    isLoading,
    error,
    refetch: refresh,
  } = useApi<EntityPermission[]>(fetcher);

  return {
    promptUserPermissions: data ?? [],
    isLoading,
    error,
    refresh,
  };
}
