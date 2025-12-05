import { fetchCurrentUser } from "../services/user-service";
import type { CurrentUser } from "../../shared/types/user";
import { useApi } from "./use-api";

export function useCurrentUser() {
  const {
    data: currentUser,
    isLoading,
    error,
    refetch: refresh,
  } = useApi<CurrentUser>(fetchCurrentUser);
  return { currentUser, isLoading, error, refresh };
}
