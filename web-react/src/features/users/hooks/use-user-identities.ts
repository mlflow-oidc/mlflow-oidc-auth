import { useCallback, useEffect, useState } from "react";
import { listUserIdentities } from "../services/user-identity-service";
import type { UserIdentity } from "../services/user-identity-service";

type Loaded = {
  username: string;
  identities: UserIdentity[];
  error: Error | null;
};

/**
 * The identities bound to a user, fetched while `username` is set (the identities modal is open).
 * Results are keyed by the username they were fetched for, so switching users never shows
 * the previous user's identities, not even for one render.
 */
export function useUserIdentities(username: string | null) {
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (!username) return;
    const controller = new AbortController();

    const load = async () => {
      setIsLoading(true);
      try {
        const identities = await listUserIdentities(
          username,
          controller.signal,
        );
        if (!controller.signal.aborted) {
          setLoaded({ username, identities, error: null });
        }
      } catch (err) {
        if (!controller.signal.aborted) {
          setLoaded({
            username,
            identities: [],
            error: err instanceof Error ? err : new Error(String(err)),
          });
        }
      } finally {
        if (!controller.signal.aborted) setIsLoading(false);
      }
    };

    void load();
    return () => controller.abort();
  }, [username, reloadKey]);

  const refresh = useCallback(() => setReloadKey((key) => key + 1), []);
  const current = loaded && loaded.username === username ? loaded : null;

  return {
    identities: current?.identities ?? [],
    isLoading: !!username && (isLoading || !current),
    error: current?.error ?? null,
    refresh,
  };
}
