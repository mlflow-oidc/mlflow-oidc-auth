import { fetchAllSkills } from "../services/skill-service";
import type { SkillListItem } from "../../shared/types/entity";
import { useApi } from "./use-api";

export function useAllSkills() {
  const {
    data: allSkills,
    isLoading,
    error,
    refetch: refresh,
  } = useApi<SkillListItem[]>(fetchAllSkills);

  return { allSkills, isLoading, error, refresh };
}
