import { http } from "./http";
import { getRuntimeConfig } from "../../shared/services/runtime-config";
import { API_ENDPOINTS } from "../configs/api-endpoints";

function buildQueryString(
  params: Record<string, string | number | boolean>
): string {
  const searchParams = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null) {
      searchParams.append(key, String(value));
    }
  }
  const queryString = searchParams.toString();
  return queryString ? `?${queryString}` : "";
}

type FetcherConfig<T> = {
  endpointKey: keyof typeof API_ENDPOINTS;
  responseType: T;
  queryParams?: Record<string, string | number | boolean>;
  headers?: Record<string, string>;
};

export function createApiFetcher<T>({
  endpointKey,
  queryParams = {},
  headers = {},
}: FetcherConfig<T>) {
  return async function fetcher(signal?: AbortSignal): Promise<T> {
    const cfg = await getRuntimeConfig(signal);

    let url = `${cfg.basePath}${API_ENDPOINTS[endpointKey]}`;

    const queryString = buildQueryString(queryParams);
    url += queryString;

    return http<T>(url, {
      method: "GET",
      signal,
      headers: {
        ...headers,
      },
    });
  };
}
