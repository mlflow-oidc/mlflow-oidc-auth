import type { EntityPermission } from "../../shared/types/entity";
import { fetchGroupSkillPermissions } from "../services/skill-service";
import { useApi } from "./use-api";
import { useCallback } from "react";

interface UseGroupSkillPermissionsProps {
  groupName: string | null;
}

export function useGroupSkillPermissions({
  groupName,
}: UseGroupSkillPermissionsProps) {
  const fetcher = useCallback(
    (signal?: AbortSignal) => {
      if (groupName === null) {
        return Promise.resolve([]) as Promise<EntityPermission[]>;
      }
      return fetchGroupSkillPermissions(groupName, signal);
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
