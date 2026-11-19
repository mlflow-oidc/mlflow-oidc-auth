import type { EntityPermission } from "../../shared/types/entity";
import { fetchSkillUserPermissions } from "../services/skill-service";
import { useApi } from "./use-api";
import { useCallback } from "react";

interface UseSkillUserPermissionsProps {
  name: string | null;
}

export function useSkillUserPermissions({
  name,
}: UseSkillUserPermissionsProps) {
  const fetcher = useCallback(
    (signal?: AbortSignal) => {
      if (name === null) {
        return Promise.resolve([]) as Promise<EntityPermission[]>;
      }
      return fetchSkillUserPermissions(name, signal);
    },
    [name],
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
