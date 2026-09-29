import { useCallback, useMemo, useState } from "react";
import type { PagedFetcher, PagedResult } from "../services/paged-list";
import type { TablePagination } from "../../shared/types/table";
import { useApi } from "./use-api";
import { usePageSize } from "./use-page-size";

/**
 * Page through a server-paginated list endpoint.
 *
 * Owns the current page (1-based) and follows the shared rows-per-page preference. The page
 * resets to 1 whenever `search` or the page size changes, and moves back to the last page if the
 * current one turns out to be past the end (e.g. after deleting the last row of the last page).
 * A page size of `"all"` omits `limit`, so the endpoint returns the full list.
 *
 * @param fetchPage - Stable fetcher (module-level, or memoised by the caller).
 * @param search - Submitted search term, sent to the server; empty means no filter.
 * @returns The current page's items, the total, loading state and the `pagination` prop for
 *   `EntityListTable`. `isLoading` is only true while nothing has been loaded yet, so previous
 *   rows stay on screen while the next page is fetched (`isFetching`).
 */
export function usePagedList<T>(fetchPage: PagedFetcher<T>, search = "") {
  const { pageSize } = usePageSize();

  // Keyed page state: a new search or page size starts again from page 1
  // without an extra effect-driven render.
  const resetKey = `${String(pageSize)}\u0000${search}`;
  const [pageState, setPageState] = useState({ key: resetKey, page: 1 });
  const page = pageState.key === resetKey ? pageState.page : 1;
  const setPage = useCallback(
    (next: number) => setPageState({ key: resetKey, page: Math.max(1, next) }),
    [resetKey],
  );

  const limit = pageSize === "all" ? undefined : pageSize;
  const offset = limit === undefined ? undefined : (page - 1) * limit;

  const fetcher = useCallback(
    (signal?: AbortSignal) => fetchPage({ limit, offset, search }, signal),
    [fetchPage, limit, offset, search],
  );
  const { data, isLoading, error, refetch } = useApi<PagedResult<T>>(fetcher);

  const items = useMemo(() => data?.items ?? [], [data]);
  const total = data?.total ?? 0;

  // Past the end (rows removed since the page was chosen, e.g. the last row
  // of the last page was deleted): move to the last page. Adjusting state
  // during render, as React recommends over an effect for derived resets.
  if (
    data &&
    !isLoading &&
    limit !== undefined &&
    page > 1 &&
    data.items.length === 0
  ) {
    const lastPage = Math.max(1, Math.ceil(data.total / limit));
    if (lastPage < page) setPageState({ key: resetKey, page: lastPage });
  }

  const pagination: TablePagination = useMemo(
    () => ({ total, page, pageSize, onPageChange: setPage }),
    [total, page, pageSize, setPage],
  );

  return {
    items,
    total,
    page,
    pageSize,
    setPage,
    pagination,
    isLoading: isLoading && data === null,
    isFetching: isLoading,
    error,
    refresh: refetch,
  };
}
