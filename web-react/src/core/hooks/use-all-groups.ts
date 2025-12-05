import { fetchAllGroups } from "../services/entity-service";
import { useApi } from "./use-api";

export function useAllGroups() {
  const {
    data: allGroups,
    isLoading,
    error,
    refetch: refresh,
  } = useApi<string[]>(fetchAllGroups);

  return { allGroups, isLoading, error, refresh };
}
