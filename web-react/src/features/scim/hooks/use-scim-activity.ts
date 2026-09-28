import { useCallback, useEffect, useRef, useState } from "react";
import { fetchScimActivity } from "../services/scim-activity-service";
import { useAuth } from "../../../core/hooks/use-auth";
import type {
  ScimActivityEntry,
  ScimActivityOutcome,
} from "../../../shared/types/scim";

export const SCIM_ACTIVITY_PAGE_SIZE = 50;

function toError(err: unknown): Error {
  return err instanceof Error ? err : new Error(String(err));
}

/**
 * The SCIM activity log, newest first, filtered by outcome, with "load more" paging on the
 * server's `next_before` cursor. Changing the filter starts over from the newest row.
 */
export function useScimActivity(outcome: ScimActivityOutcome | null) {
  const { isAuthenticated } = useAuth();
  const [entries, setEntries] = useState<ScimActivityEntry[]>([]);
  const [nextBefore, setNextBefore] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  // Bumped on every first-page load, so a "load more" answer for a filter that is no longer
  // selected is dropped instead of appended.
  const generation = useRef(0);
  // The paging cursor, tagged with the first-page load it came from. "Load more" uses it only
  // while that load is still the current one, so a cursor left over from the previous filter
  // (or from before a Refresh) can never fetch a page into the new list.
  const cursor = useRef<{ generation: number; before: number | null }>({
    generation: 0,
    before: null,
  });

  useEffect(() => {
    if (!isAuthenticated) return;
    const controller = new AbortController();
    const current = ++generation.current;

    const load = async () => {
      cursor.current = { generation: current, before: null };
      setNextBefore(null);
      setIsLoading(true);
      setError(null);
      try {
        const page = await fetchScimActivity(
          { limit: SCIM_ACTIVITY_PAGE_SIZE, outcome: outcome ?? undefined },
          controller.signal,
        );
        if (current !== generation.current) return;
        cursor.current = { generation: current, before: page.next_before };
        setEntries(page.activity);
        setNextBefore(page.next_before);
      } catch (err) {
        if (current !== generation.current || controller.signal.aborted) return;
        setError(toError(err));
        setEntries([]);
        setNextBefore(null);
      } finally {
        if (current === generation.current) setIsLoading(false);
      }
    };

    void load();
    return () => controller.abort();
  }, [isAuthenticated, outcome, reloadKey]);

  const loadMore = useCallback(async () => {
    const current = generation.current;
    const { generation: cursorGeneration, before } = cursor.current;
    // No cursor yet for the current first-page load (it is still in flight), or none left.
    if (cursorGeneration !== current || before === null) return;
    setIsLoadingMore(true);
    try {
      const page = await fetchScimActivity({
        limit: SCIM_ACTIVITY_PAGE_SIZE,
        before,
        outcome: outcome ?? undefined,
      });
      if (current !== generation.current) return;
      cursor.current = { generation: current, before: page.next_before };
      setEntries((previous) => [...previous, ...page.activity]);
      setNextBefore(page.next_before);
    } catch (err) {
      if (current === generation.current) setError(toError(err));
    } finally {
      setIsLoadingMore(false);
    }
  }, [outcome]);

  const refresh = useCallback(() => setReloadKey((key) => key + 1), []);

  return {
    entries,
    hasMore: nextBefore !== null,
    isLoading,
    isLoadingMore,
    error,
    loadMore,
    refresh,
  };
}
