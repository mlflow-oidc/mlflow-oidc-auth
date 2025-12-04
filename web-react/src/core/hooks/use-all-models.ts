import type { ModelListItem } from "../../shared/types/entity";
import { fetchAllModels } from "../services/entity-service";

import { useApi } from "./use-api";

export function useAllModels(shouldFetch: boolean) {
  const {
    data: allModels,
    isLoading,
    error,
    refetch: refresh,
  } = useApi<ModelListItem[]>(shouldFetch, fetchAllModels);

  return { allModels, isLoading, error, refresh };
}
