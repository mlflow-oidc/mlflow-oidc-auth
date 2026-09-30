import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "./use-auth";
import { useSelectedWorkspace } from "../../shared/context/use-workspace";

export interface ApiState<T> {
  data: T | null;
  isLoading: boolean;
  error: Error | null;
  refetch: () => void;
  /** True when `data` came from a different fetcher or workspace than the current ones. */
  isStale: boolean;
}

type Fetcher<T> = (signal?: AbortSignal) => Promise<T>;

/** What a response was requested with: both select the data it holds. */
interface DataSource<T> {
  fetcher: Fetcher<T>;
  workspace: string | null;
}

export function useApi<T>(fetcher: Fetcher<T>): ApiState<T> {
  const [data, setData] = useState<T | null>(null);
  const [dataSource, setDataSource] = useState<DataSource<T> | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const { isAuthenticated } = useAuth();
  const selectedWorkspace = useSelectedWorkspace();

  // Only the most recent request may write state. A refetch and an
  // effect-driven fetch (e.g. a page change) can overlap; without this, the
  // one that resolves last wins, even if it was started first.
  const latestRequest = useRef<AbortController | null>(null);

  const run = useCallback((source: DataSource<T>): AbortController => {
    latestRequest.current?.abort();
    const controller = new AbortController();
    latestRequest.current = controller;
    const isCurrent = () =>
      latestRequest.current === controller && !controller.signal.aborted;

    const load = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const result = await source.fetcher(controller.signal);
        if (isCurrent()) {
          setData(result);
          setDataSource(source);
        }
      } catch (err) {
        if (isCurrent()) {
          setError(err instanceof Error ? err : new Error(String(err)));
          setData(null);
          setDataSource(source);
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
      const controller = run({ fetcher, workspace: selectedWorkspace });
      return () => controller.abort();
    }
  }, [isAuthenticated, fetcher, selectedWorkspace, run]);

  const refetch = useCallback(() => {
    run({ fetcher, workspace: selectedWorkspace });
  }, [run, fetcher, selectedWorkspace]);

  // The workspace matters as much as the fetcher: a paged list keeps the same
  // fetcher across a workspace switch, but its data belongs to the old one.
  const isStale =
    dataSource !== null &&
    (dataSource.fetcher !== fetcher ||
      dataSource.workspace !== selectedWorkspace);

  return { data, isLoading, error, refetch, isStale };
}
