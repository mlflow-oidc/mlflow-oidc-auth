import { useEffect } from "react";
import { useUserData } from "../../../shared/context/use-user-data";
import { fetchCurrentUser } from "../services/auth-service";
import { useAuth } from "./use-auth";

export const useLoadCurrentUser = () => {
  const { isAuthenticated } = useAuth();
  const { currentUser, isLoading, setCurrentUser, setIsLoading, setError } =
    useUserData();

  useEffect(() => {
    if (isAuthenticated && !currentUser && !isLoading) {
      const abortController = new AbortController();

      const loadUser = async () => {
        setIsLoading(true);
        setError(null);
        try {
          const user = await fetchCurrentUser(abortController.signal);
          setCurrentUser(user);
        } catch (err) {
          if (!abortController.signal.aborted) {
            console.error("useLoadCurrentUser: failed to load user info", err);
            setError(
              err instanceof Error
                ? err
                : new Error(`Failed to fetch user: ${String(err)}`)
            );
            setCurrentUser(null);
          }
        } finally {
          if (!abortController.signal.aborted) {
            setIsLoading(false);
          }
        }
      };

      void loadUser();
      return () => abortController.abort();
    }
  }, [
    isAuthenticated,
    currentUser,
    isLoading,
    setCurrentUser,
    setIsLoading,
    setError,
  ]);
};
