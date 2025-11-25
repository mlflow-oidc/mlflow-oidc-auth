import { useCallback, useEffect, useState } from "react";
import { fetchCurrentUser } from "../services/auth-service";
import type { CurrentUser } from "../../../shared/types/user";

export function useCurrentUser(isAuthenticated: boolean) {
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (isAuthenticated && !currentUser) {
      const controller = new AbortController();

      const fetchUser = async () => {
        setIsLoading(true);
        setError(null);

        try {
          const data = await fetchCurrentUser(controller.signal);
          setCurrentUser(data);
        } catch (err) {
          if (!controller.signal.aborted) {
            setError(err instanceof Error ? err : new Error(String(err)));
            setCurrentUser(null);
          }
        } finally {
          if (!controller.signal.aborted) {
            setIsLoading(false);
          }
        }
      };

      void fetchUser();

      return () => controller.abort();
    }
  }, [isAuthenticated, currentUser]);

  const refresh = useCallback(() => {
    const controller = new AbortController();
    fetchCurrentUser(controller.signal)
      .then(setCurrentUser)
      .catch((err) => {
        if (!controller.signal.aborted)
          setError(err instanceof Error ? err : new Error(String(err)));
      });
  }, []);

  return { currentUser, isLoading, error, refresh };
}
