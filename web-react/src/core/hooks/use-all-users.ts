import { fetchAllUsers } from "../services/user-service";
import { useApi } from "./use-api";

export function useAllUsers() {
  const {
    data: allUsers,
    isLoading,
    error,
    refetch: refresh,
  } = useApi<string[]>(fetchAllUsers);

  return { allUsers, isLoading, error, refresh };
}
