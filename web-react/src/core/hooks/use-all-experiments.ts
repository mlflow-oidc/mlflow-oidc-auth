import { fetchAllExperiments } from "../services/entity-service";
import type { ExperimentListItem } from "../../shared/types/entity";
import { useApi } from "./use-api";

export function useAllExperiments() {
  const {
    data: allExperiments,
    isLoading,
    error,
    refetch: refresh,
  } = useApi<ExperimentListItem[]>(fetchAllExperiments);

  return { allExperiments, isLoading, error, refresh };
}
