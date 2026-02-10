import {
  STATIC_API_ENDPOINTS,
  DYNAMIC_API_ENDPOINTS,
  type PathParams,
  type DynamicEndpointKey,
} from "../configs/api-endpoints";
import type { StaticFetcherConfig, DynamicFetcherConfig } from "../types/api";
import { request } from "./api-utils";

export function createStaticApiFetcher<T>({
  endpointKey,
  queryParams = {},
  headers = {},
}: StaticFetcherConfig<T>) {
  const endpointPath = STATIC_API_ENDPOINTS[endpointKey];

  return async function fetcher(signal?: AbortSignal): Promise<T> {
    return request<T>(endpointPath, {
      queryParams,
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
      endpointFunction.length,
    ) as PathParams<K>;
    const signal = args[endpointFunction.length] as AbortSignal | undefined;

    const endpointPath = (
      endpointFunction as (...args: PathParams<K>) => string
    )(...pathParamsTuple);

    return request<T>(endpointPath, {
      queryParams,
      method: "GET",
      signal,
      headers: {
        ...headers,
      },
    });
  };
}
