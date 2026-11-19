import type { EntityPermission } from "../../shared/types/entity";
import { fetchSkillGroupPermissions } from "../services/skill-service";
import { useApi } from "./use-api";
import { useCallback } from "react";

interface UseSkillGroupPermissionsProps {
  name: string | null;
}

export function useSkillGroupPermissions({
  name,
}: UseSkillGroupPermissionsProps) {
  const fetcher = useCallback(
    (signal?: AbortSignal) => {
      if (name === null) {
        return Promise.resolve([]) as Promise<EntityPermission[]>;
      }
      return fetchSkillGroupPermissions(name, signal);
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
