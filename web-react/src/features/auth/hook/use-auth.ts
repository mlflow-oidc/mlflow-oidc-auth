import { useEffect, useState } from "react";
import { fetchAuthStatus } from "../service/auth-service";

type UseAuthResult = {
  loading: boolean;
  authenticated: boolean | null;
};

const useAuth = (): UseAuthResult => {
  const [loading, setLoading] = useState(true);
  const [authenticated, setAuthenticated] = useState<boolean | null>(null);

  useEffect(() => {
    const abortController = new AbortController();

    async function init() {
      setLoading(true);
      try {
        const { authenticated } = await fetchAuthStatus(abortController.signal);
        setAuthenticated(authenticated);
      } catch (err) {
        if (!abortController.signal.aborted) {
          console.error("useAuth: failed to load auth status", err);
          setAuthenticated(false);
        }
      } finally {
        if (!abortController.signal.aborted) {
          setLoading(false);
        }
      }
    }

    void init();

    return () => {
      abortController.abort();
    };
  }, []);

  return { loading, authenticated };
};

export { useAuth };
