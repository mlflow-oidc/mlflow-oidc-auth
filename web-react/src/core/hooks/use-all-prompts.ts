import type { PromptListItem } from "../../shared/types/entity";
import { fetchAllPrompts } from "../services/entity-service";
import { useApi } from "./use-api";

export function useAllPrompts() {
  const {
    data: allPrompts,
    isLoading,
    error,
    refetch: refresh,
  } = useApi<PromptListItem[]>(fetchAllPrompts);

  return { allPrompts, isLoading, error, refresh };
}
