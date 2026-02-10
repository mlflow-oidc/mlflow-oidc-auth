import { fetchDeletedRuns } from "../services/trash-service";
import type { DeletedRun } from "../../shared/types/entity";
import { useApi } from "./use-api";

export function useDeletedRuns() {
  const {
    data: response,
    isLoading,
    error,
    refetch: refresh,
  } = useApi<{ deleted_runs: DeletedRun[] }>(fetchDeletedRuns);

  return {
    deletedRuns: response?.deleted_runs || [],
    isLoading,
    error,
    refresh,
  };
}
