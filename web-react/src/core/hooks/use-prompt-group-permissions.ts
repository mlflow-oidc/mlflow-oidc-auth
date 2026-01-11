import type { EntityPermission } from "../../shared/types/entity";
import { fetchPromptGroupPermissions } from "../services/entity-service";
import { useApi } from "./use-api";
import { useCallback } from "react";

interface UsePromptGroupPermissionsProps {
  promptName: string | null;
}

export function usePromptGroupPermissions({
  promptName,
}: UsePromptGroupPermissionsProps) {
  const fetcher = useCallback(
    (signal?: AbortSignal) => {
      if (promptName === null) {
        return Promise.resolve([]) as Promise<EntityPermission[]>;
      }
      return fetchPromptGroupPermissions(promptName, signal);
    },
    [promptName]
  );

  const {
    data,
    isLoading,
    error,
    refetch: refresh,
  } = useApi<EntityPermission[]>(fetcher);

  return {
    promptGroupPermissions: data ?? [],
    isLoading,
    error,
    refresh,
  };
}
