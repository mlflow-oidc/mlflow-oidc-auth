import { fetchAllGatewayEndpoints } from "../services/gateway-service";
import type { GatewayEndpointListItem } from "../../shared/types/entity";
import { useApi } from "./use-api";

export function useAllGatewayEndpoints() {
  const {
    data: allGatewayEndpoints,
    isLoading,
    error,
    refetch: refresh,
  } = useApi<GatewayEndpointListItem[]>(fetchAllGatewayEndpoints);

  return { allGatewayEndpoints, isLoading, error, refresh };
}
