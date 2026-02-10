import { getRuntimeConfig } from "../../shared/services/runtime-config";
import type { QueryParams } from "../types/api";
import { http, type RequestOptions } from "./http";

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
  signal?: AbortSignal,
): Promise<string> {
  const cfg = await getRuntimeConfig(signal);
  return `${cfg.basePath}${endpoint}${buildQueryString(queryParams)}`;
}

export async function request<T>(
  endpoint: string,
  options: RequestOptions & { queryParams?: QueryParams } = {},
): Promise<T> {
  const { queryParams, ...httpOptions } = options;
  const url = await resolveUrl(
    endpoint,
    queryParams || {},
    options.signal || undefined,
  );
  return http<T>(url, httpOptions);
}
