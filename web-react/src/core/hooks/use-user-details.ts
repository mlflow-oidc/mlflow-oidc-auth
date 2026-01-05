import { useCallback } from "react";
import { fetchUserDetails } from "../services/user-service";
import { useApi } from "./use-api";
import type { CurrentUser } from "../../shared/types/user";

export function useUserDetails({ username }: { username: string | null }) {
  const fetcher = useCallback(
    (signal?: AbortSignal) => {
      if (!username) {
        return Promise.reject(new Error("Username is required"));
      }
      return fetchUserDetails(username, signal);
    },
    [username]
  );

  const {
    data: user,
    isLoading,
    error,
    refetch,
  } = useApi<CurrentUser>(fetcher);

  return { user, isLoading, error, refetch };
}
