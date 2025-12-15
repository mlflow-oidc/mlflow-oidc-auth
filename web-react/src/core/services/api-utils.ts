import { http } from "./http";
import { getRuntimeConfig } from "../../shared/services/runtime-config";
import {
  STATIC_API_ENDPOINTS,
  DYNAMIC_API_ENDPOINTS,
  type PathParams,
  type DynamicEndpointKey,
} from "../configs/api-endpoints";
import type {
  QueryParams,
  StaticFetcherConfig,
  DynamicFetcherConfig,
} from "../types/api";

function buildQueryString(params: QueryParams): string {
  const searchParams = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null) {
      searchParams.append(key, String(value));
    }
  }
  const queryString = searchParams.toString();
  return queryString ? `?${queryString}` : "";
}

export async function resolveUrl(
  endpoint: string,
  queryParams: QueryParams,
  signal?: AbortSignal
): Promise<string> {
  const cfg = await getRuntimeConfig(signal);
  return `${cfg.basePath}${endpoint}${buildQueryString(queryParams)}`;
}

export function createStaticApiFetcher<T>({
  endpointKey,
  queryParams = {},
  headers = {},
}: StaticFetcherConfig<T>) {
  const endpointPath = STATIC_API_ENDPOINTS[endpointKey];

  return async function fetcher(signal?: AbortSignal): Promise<T> {
    const url = await resolveUrl(endpointPath, queryParams, signal);
    return http<T>(url, {
      method: "GET",
      signal,
      headers: {
        ...headers,
      },
    });
  };
}

export function createDynamicApiFetcher<T, K extends DynamicEndpointKey>({
  endpointKey,
  queryParams = {},
  headers = {},
}: DynamicFetcherConfig<T, K>) {
  const endpointFunction = DYNAMIC_API_ENDPOINTS[endpointKey];

  return async function fetcher(
    ...args: [...PathParams<K>, signal?: AbortSignal]
  ): Promise<T> {
    const pathParamsTuple = args.slice(
      0,
      endpointFunction.length
    ) as PathParams<K>;
    const signal = args[endpointFunction.length] as AbortSignal | undefined;

    const endpointPath = (
      endpointFunction as (...args: PathParams<K>) => string
    )(...pathParamsTuple);

    const url = await resolveUrl(endpointPath, queryParams, signal);

    return http<T>(url, {
      method: "GET",
      signal,
      headers: {
        ...headers,
      },
    });
  };
}
