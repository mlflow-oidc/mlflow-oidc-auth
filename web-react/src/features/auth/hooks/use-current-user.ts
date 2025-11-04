import { useEffect, useState } from "react";
import { fetchCurrentUser } from "../services/auth-service";
import type { CurrentUser } from "../../../shared/types/user";

type UseCurrentUserResult = {
  loading: boolean;
  currentUser: CurrentUser | null;
  error: Error | null;
};

const useCurrentUser = (): UseCurrentUserResult => {
  const [loading, setLoading] = useState(true);
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    const abortController = new AbortController();

    async function loadCurrentUser() {
      setLoading(true);
      setError(null);
      try {
        const user = await fetchCurrentUser(abortController.signal);
        setCurrentUser(user);
      } catch (err) {
        if (!abortController.signal.aborted) {
          console.error("useCurrentUser: failed to load user info", err);
          setError(err as Error);
          setCurrentUser(null);
        }
      } finally {
        if (!abortController.signal.aborted) {
          setLoading(false);
        }
      }
    }

    void loadCurrentUser();

    return () => {
      abortController.abort();
    };
  }, []);

  return { loading, currentUser, error };
};

export { useCurrentUser };
