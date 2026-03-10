import { fetchAllGatewayModels } from "../services/gateway-service";
import type { GatewayModelListItem } from "../../shared/types/entity";
import { useApi } from "./use-api";

export function useAllGatewayModels() {
  const {
    data: allGatewayModels,
    isLoading,
    error,
    refetch: refresh,
  } = useApi<GatewayModelListItem[]>(fetchAllGatewayModels);

  return { allGatewayModels, isLoading, error, refresh };
}
