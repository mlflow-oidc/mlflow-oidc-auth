import { useState, useEffect, useCallback } from "react";
import { http, type RequestOptions } from "../services/http";

type UseApiOptions<T> = RequestOptions & {
  manual?: boolean;
  initialData?: T;
  onSuccess?: (data: T) => void;
};

export function useApi<T = unknown>(
  url: string,
  options: UseApiOptions<T> = {}
) {
  const { manual = false, initialData, onSuccess, ...requestOptions } = options;

  const [data, setData] = useState<T | null>(initialData ?? null);
  const [loading, setLoading] = useState(!manual);
  const [error, setError] = useState<Error | null>(null);

  const run = useCallback(async () => {
    if (!url) return;

    setLoading(true);
    setError(null);

    try {
      const result = await http<T>(url, requestOptions);
      setData(result);
      onSuccess?.(result);
      return result;
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
      throw err;
    } finally {
      setLoading(false);
    }
  }, [onSuccess, requestOptions, url]);

  useEffect(() => {
    if (!manual && url) {
      void run();
    }
  }, [manual, url, run]);

  return { data, loading, error, run };
}
