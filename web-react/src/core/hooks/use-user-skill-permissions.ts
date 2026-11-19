import type { EntityPermission } from "../../shared/types/entity";
import { fetchUserSkillPermissions } from "../services/skill-service";
import { useApi } from "./use-api";
import { useCallback } from "react";

interface UseUserSkillPermissionsProps {
  username: string | null;
}

export function useUserSkillPermissions({
  username,
}: UseUserSkillPermissionsProps) {
  const fetcher = useCallback(
    (signal?: AbortSignal) => {
      if (username === null) {
        return Promise.resolve([]) as Promise<EntityPermission[]>;
      }
      return fetchUserSkillPermissions(username, signal);
    },
    [username],
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
