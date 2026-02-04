import { fetchAllGatewaySecrets } from "../services/gateway-service";
import type { GatewaySecretListItem } from "../../shared/types/entity";
import { useApi } from "./use-api";

export function useAllGatewaySecrets() {
  const {
    data: allGatewaySecrets,
    isLoading,
    error,
    refetch: refresh,
  } = useApi<GatewaySecretListItem[]>(fetchAllGatewaySecrets);

  return { allGatewaySecrets, isLoading, error, refresh };
}
