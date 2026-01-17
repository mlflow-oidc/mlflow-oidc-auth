import { fetchDeletedExperiments } from "../services/trash-service";
import type { DeletedExperiment } from "../../shared/types/entity";
import { useApi } from "./use-api";

export function useDeletedExperiments() {
  const {
    data: response,
    isLoading,
    error,
    refetch: refresh,
  } = useApi<{ deleted_experiments: DeletedExperiment[] }>(fetchDeletedExperiments);

  return {
    deletedExperiments: response?.deleted_experiments || [],
    isLoading,
    error,
    refresh
  };
}
