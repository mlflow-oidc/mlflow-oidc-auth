import { fetchAllServiceAccounts } from "../services/user-service";
import { useApi } from "./use-api";

export function useAllServiceAccounts() {
  const {
    data: allServiceAccounts,
    isLoading,
    error,
    refetch: refresh,
  } = useApi<string[]>(fetchAllServiceAccounts);

  return { allServiceAccounts, isLoading, error, refresh };
}
