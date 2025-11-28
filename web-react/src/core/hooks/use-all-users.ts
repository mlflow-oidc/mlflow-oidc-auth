import { fetchAllUsers } from "../services/user-service";
import { useApi } from "./use-api";

export function useAllUsers(shouldFetch: boolean) {
  const {
    data: allUsers,
    isLoading,
    error,
    refetch: refresh,
  } = useApi<string[]>(shouldFetch, fetchAllUsers);

  return { allUsers, isLoading, error, refresh };
}
