import { useApi } from "../../../core/hooks/use-api";
import {
  fetchServiceAccountSources,
  type ServiceAccountSource,
} from "../services/service-account-source-service";

/** The sources a service account can sign in through (admin only). */
export function useServiceAccountSources(): {
  sources: ServiceAccountSource[];
  isLoading: boolean;
} {
  const { data, isLoading } = useApi(fetchServiceAccountSources);
  return { sources: data ?? [], isLoading };
}
