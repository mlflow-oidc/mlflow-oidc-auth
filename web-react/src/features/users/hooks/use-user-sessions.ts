import { useCallback, useEffect, useState } from "react";
import { listUserSessions } from "../services/user-session-service";
import type { UserSession } from "../../../shared/types/user";

type Loaded = {
  username: string;
  sessions: UserSession[];
  error: Error | null;
};

/**
 * A user's live sessions, fetched while `username` is set (the sessions modal is open).
 * Results are keyed by the username they were fetched for, so switching users never shows
 * the previous user's sessions, not even for one render.
 */
export function useUserSessions(username: string | null) {
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (!username) return;
    const controller = new AbortController();

    const load = async () => {
      setIsLoading(true);
      try {
        const sessions = await listUserSessions(username, controller.signal);
        if (!controller.signal.aborted) {
          setLoaded({ username, sessions, error: null });
        }
      } catch (err) {
        if (!controller.signal.aborted) {
          setLoaded({
            username,
            sessions: [],
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
    sessions: current?.sessions ?? [],
    isLoading: !!username && (isLoading || !current),
    error: current?.error ?? null,
    refresh,
  };
}
