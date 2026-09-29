import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "./use-auth";
import { useSelectedWorkspace } from "../../shared/context/use-workspace";

export interface ApiState<T> {
  data: T | null;
  isLoading: boolean;
  error: Error | null;
  refetch: () => void;
  /** True when `data` came from a different fetcher than the current one. */
  isStale: boolean;
}

type Fetcher<T> = (signal?: AbortSignal) => Promise<T>;

export function useApi<T>(fetcher: Fetcher<T>): ApiState<T> {
  const [data, setData] = useState<T | null>(null);
  const [dataSource, setDataSource] = useState<Fetcher<T> | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const { isAuthenticated } = useAuth();
  const selectedWorkspace = useSelectedWorkspace();

  // Only the most recent request may write state. A refetch and an
  // effect-driven fetch (e.g. a page change) can overlap; without this, the
  // one that resolves last wins, even if it was started first.
  const latestRequest = useRef<AbortController | null>(null);

  const run = useCallback((source: Fetcher<T>): AbortController => {
    latestRequest.current?.abort();
    const controller = new AbortController();
    latestRequest.current = controller;
    const isCurrent = () =>
      latestRequest.current === controller && !controller.signal.aborted;

    const load = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const result = await source(controller.signal);
        if (isCurrent()) {
          setData(result);
          setDataSource(() => source);
        }
      } catch (err) {
        if (isCurrent()) {
          setError(err instanceof Error ? err : new Error(String(err)));
          setData(null);
          setDataSource(() => source);
        }
      } finally {
        if (isCurrent()) {
          setIsLoading(false);
        }
      }
    };
    void load();
    return controller;
  }, []);

  useEffect(() => {
    if (isAuthenticated) {
      const controller = run(fetcher);
      return () => controller.abort();
    }
  }, [isAuthenticated, fetcher, selectedWorkspace, run]);

  const refetch = useCallback(() => {
    run(fetcher);
  }, [run, fetcher]);

  const isStale = dataSource !== null && dataSource !== fetcher;

  return { data, isLoading, error, refetch, isStale };
}
