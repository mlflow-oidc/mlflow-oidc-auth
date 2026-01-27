import { useCallback, useEffect, useState } from "react";
import { useAuth } from "./use-auth";

export interface ApiState<T> {
  data: T | null;
  isLoading: boolean;
  error: Error | null;
  refetch: () => void;
}

export function useApi<T>(
  fetcher: (signal?: AbortSignal) => Promise<T>,
): ApiState<T> {
  const [data, setData] = useState<T | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const { isAuthenticated } = useAuth();

  const initialFetcher = useCallback(fetcher, [fetcher]);

  useEffect(() => {
    if (isAuthenticated) {
      const controller = new AbortController();
      let aborted = false;

      const fetchData = async () => {
        setIsLoading(true);
        setError(null);

        try {
          const result = await initialFetcher(controller.signal);
          if (!aborted) {
            setData(result);
          }
        } catch (err) {
          if (!aborted) {
            setError(err instanceof Error ? err : new Error(String(err)));
            setData(null);
          }
        } finally {
          if (!aborted) {
            setIsLoading(false);
          }
        }
      };

      void fetchData();

      return () => {
        aborted = true;
        controller.abort();
      };
    }
  }, [isAuthenticated, initialFetcher]);

  const refetch = useCallback(() => {
    setIsLoading(true);
    setError(null);
    const controller = new AbortController();
    fetcher(controller.signal)
      .then((result) => {
        setData(result);
      })
      .catch((err) => {
        if (!controller.signal.aborted) {
          setError(err instanceof Error ? err : new Error(String(err)));
          setData(null);
        }
      })
      .finally(() => {
        setIsLoading(false);
      });
  }, [fetcher]);

  return { data, isLoading, error, refetch };
}
