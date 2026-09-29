import type { QueryParams } from "../types/api";
import { requestWithHeaders } from "./api-utils";

/** Response header carrying the number of items that match the query, across all pages. */
export const TOTAL_COUNT_HEADER = "X-Total-Count";

/** The largest page the server accepts (`MAX_PAGE_SIZE` on the backend). */
export const MAX_SERVER_PAGE_SIZE = 500;

/**
 * Pagination and search parameters for a list endpoint. Omitting `limit` asks for the full list,
 * exactly as before the endpoint supported pagination.
 */
export interface ListQuery {
  limit?: number;
  offset?: number;
  /** Case-insensitive substring match on the list's display key (name, username, ...). */
  search?: string;
}

/** One page of a list plus the total number of matching items. */
export interface PagedResult<T> {
  items: T[];
  total: number;
}

/** A list fetcher usable by `usePagedList`. */
export type PagedFetcher<T> = (
  query: ListQuery,
  signal?: AbortSignal,
) => Promise<PagedResult<T>>;

interface PagedListOptions<TBody, TItem> {
  /** Pull the items out of the response body (a bare array, or e.g. `body.tokens`). */
  extract: (body: TBody) => TItem[];
  /**
   * The display key the server searches on. Used only when the server did not paginate (no
   * `X-Total-Count`), so the same search and paging can be applied locally.
   */
  displayKey: (item: TItem) => string;
  /** Extra query parameters the endpoint always needs (e.g. `service=true`). */
  queryParams?: QueryParams;
  /**
   * The endpoint does not return its full list without `limit` (webhooks: MLflow's own default
   * page applies). "All" then walks the server's pages instead of asking once without `limit`.
   */
  fullListNeedsPaging?: boolean;
}

/** Turn a {@link ListQuery} into query parameters, leaving out what is not set. */
export function listQueryParams(query: ListQuery): QueryParams {
  const params: QueryParams = {};
  if (query.limit !== undefined) {
    params.limit = query.limit;
    params.offset = query.offset ?? 0;
  }
  if (query.search) params.search = query.search;
  return params;
}

function parseTotal(headers: Headers | undefined): number | null {
  const raw = headers?.get(TOTAL_COUNT_HEADER)?.trim();
  if (!raw || !/^\d+$/.test(raw)) return null;
  return Number(raw);
}

/**
 * Fetch one page of a list endpoint.
 *
 * When the response carries `X-Total-Count` the body is already the requested page. When it does
 * not (a backend without pagination, or a full-list request) the body is treated as the complete
 * list: the search and the page window are applied here, so callers see the same result either way.
 *
 * @param endpoint - The endpoint path (resolved against the runtime base path).
 * @param query - Page window and search term.
 * @param options - How to read items out of the body and what the display key is.
 * @param signal - Optional abort signal.
 * @returns The page's items and the total number of matching items.
 */
export async function fetchPagedList<TBody, TItem>(
  endpoint: string,
  query: ListQuery,
  options: PagedListOptions<TBody, TItem>,
  signal?: AbortSignal,
): Promise<PagedResult<TItem>> {
  if (query.limit === undefined && options.fullListNeedsPaging) {
    return fetchEveryPage(endpoint, query, options, signal);
  }
  const { data, headers } = await requestWithHeaders<TBody>(endpoint, {
    method: "GET",
    queryParams: { ...options.queryParams, ...listQueryParams(query) },
    signal,
  });
  const items = options.extract(data);

  const total = parseTotal(headers);
  if (total !== null) return { items, total };

  const term = query.search?.toLowerCase() ?? "";
  const matching = term
    ? items.filter((item) =>
        options.displayKey(item).toLowerCase().includes(term),
      )
    : items;
  if (query.limit === undefined) {
    return { items: matching, total: matching.length };
  }
  const offset = query.offset ?? 0;
  return {
    items: matching.slice(offset, offset + query.limit),
    total: matching.length,
  };
}

/**
 * The whole list, walked in the largest pages the server allows, for endpoints whose unpaged
 * response is not the full list. Stops when the reported total is reached or a page comes back
 * empty, so a list that shrinks mid-walk cannot loop.
 */
async function fetchEveryPage<TBody, TItem>(
  endpoint: string,
  query: ListQuery,
  options: PagedListOptions<TBody, TItem>,
  signal?: AbortSignal,
): Promise<PagedResult<TItem>> {
  const items: TItem[] = [];
  let total = 0;
  for (;;) {
    const page = await fetchPagedList<TBody, TItem>(
      endpoint,
      { ...query, limit: MAX_SERVER_PAGE_SIZE, offset: items.length },
      options,
      signal,
    );
    items.push(...page.items);
    total = page.total;
    if (page.items.length === 0 || items.length >= total) break;
  }
  return { items, total: Math.max(total, items.length) };
}

/**
 * Build a {@link PagedFetcher} for one list endpoint.
 */
export function createPagedFetcher<TBody, TItem>(
  endpoint: string,
  options: PagedListOptions<TBody, TItem>,
): PagedFetcher<TItem> {
  return (query, signal) =>
    fetchPagedList<TBody, TItem>(endpoint, query, options, signal);
}
