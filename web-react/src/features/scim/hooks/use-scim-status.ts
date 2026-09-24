import { fetchScimStatus } from "../services/scim-activity-service";
import type { ScimProvisioningStatus } from "../../../shared/types/scim";
import { useApi } from "../../../core/hooks/use-api";

export function useScimStatus() {
  const { data, isLoading, error, refetch } =
    useApi<ScimProvisioningStatus>(fetchScimStatus);

  return {
    status: data,
    isLoading,
    error,
    refresh: refetch,
  };
}
