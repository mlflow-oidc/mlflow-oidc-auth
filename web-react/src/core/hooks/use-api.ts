import { useCallback, useEffect, useState } from "react";
import { useAuth } from "./use-auth";

export interface ApiState<T> {
  data: T | null;
  isLoading: boolean;
  error: Error | null;
  refetch: () => void;
}

export function useApi<T>(
  fetcher: (signal?: AbortSignal) => Promise<T>
): ApiState<T> {
  const [data, setData] = useState<T | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const { isAuthenticated } = useAuth();

  const initialFetcher = useCallback(fetcher, [fetcher]);

  useEffect(() => {
    if (isAuthenticated && !data) {
      const controller = new AbortController();

      const fetchData = async () => {
        setIsLoading(true);
        setError(null);

        try {
          const data = await initialFetcher(controller.signal);
          setData(data);
        } catch (err) {
          if (!controller.signal.aborted) {
            setError(err instanceof Error ? err : new Error(String(err)));
            setData(null);
          }
        } finally {
          if (!controller.signal.aborted) {
            setIsLoading(false);
          }
        }
      };

      void fetchData();

      return () => controller.abort();
    }
  }, [isAuthenticated, data, initialFetcher]);

  const refetch = useCallback(() => {
    const controller = new AbortController();
    fetcher(controller.signal)
      .then(setData)
      .catch((err) => {
        if (!controller.signal.aborted)
          setError(err instanceof Error ? err : new Error(String(err)));
      });
  }, [fetcher]);

  return { data, isLoading, error, refetch };
}
