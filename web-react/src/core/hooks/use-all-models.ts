import type { ModelListItem } from "../../shared/types/entity";
import { fetchAllModels } from "../services/entity-service";
import { useApi } from "./use-api";

export function useAllModels() {
  const {
    data: allModels,
    isLoading,
    error,
    refetch: refresh,
  } = useApi<ModelListItem[]>(fetchAllModels);

  return { allModels, isLoading, error, refresh };
}
