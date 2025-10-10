import { useEffect, useState, useCallback } from "react";
import { fetchRuntimeConfig, buildAuthUrlWithParams } from "./auth-service";

type UseAuthResult = {
  loading: boolean;
  authenticated: boolean | null;
  user?: Record<string, unknown> | null;
  redirectToAuth: () => void;
};

const useAuth = (): UseAuthResult => {
  const [loading, setLoading] = useState(true);
  const [authenticated, setAuthenticated] = useState<boolean | null>(null);
  // const [user, setUser] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    let mounted = true;

    async function init() {
      setLoading(true);
      try {
        // Debug: fetch only the runtime config and log the full response
        const cfg = await fetchRuntimeConfig();
        console.debug("useAuth: runtime config response:", cfg);

        // Set authenticated state based on runtime config for now
        if (mounted) setAuthenticated(!!cfg?.authenticated);
      } catch (err) {
        console.error("useAuth: failed to load runtime config", err);
        if (mounted) setAuthenticated(false);
      } finally {
        if (mounted) setLoading(false);
      }
    }

    void init();
    return () => {
      mounted = false;
    };
  }, []);

  const redirectToAuth = useCallback(() => {
    try {
      const { href } = buildAuthUrlWithParams();
      // Use location.replace to avoid creating extra history entries
      if (typeof window !== "undefined") {
        // Prevent infinite redirect loop by not redirecting if already on /auth
        if (!window.location.pathname.startsWith("/auth")) {
          window.location.replace(href);
        }
      }
    } catch (err) {
      console.error("redirectToAuth failed", err);
    }
  }, []);

  return { loading, authenticated, redirectToAuth } as UseAuthResult;
};

export { useAuth };
