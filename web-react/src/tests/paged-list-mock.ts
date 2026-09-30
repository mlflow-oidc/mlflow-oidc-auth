import { vi } from "vitest";
import type { usePagedList } from "../core/hooks/use-paged-list";
import type { PagedFetcher } from "../core/services/paged-list";

export type PagedListState<T> = ReturnType<typeof usePagedList<T>>;

/**
 * A `usePagedList` result for page tests that mock the hook: one page holding `items`.
 */
export function pagedListState<T>(
  items: T[],
  overrides: Partial<PagedListState<T>> = {},
): PagedListState<T> {
  const total = overrides.total ?? items.length;
  return {
    items,
    total,
    page: 1,
    pageSize: 20,
    setPage: vi.fn(),
    pagination: { total, page: 1, pageSize: 20, onPageChange: vi.fn() },
    isLoading: false,
    isFetching: false,
    error: null,
    refresh: vi.fn(),
    ...overrides,
  };
}

/**
 * A `usePagedList` mock implementation that filters `items` by the search argument the way the
 * server does (case-insensitive substring on the display key).
 */
export function serverSearch<T>(
  items: T[],
  displayKey: (item: T) => string,
  overrides: Partial<PagedListState<T>> = {},
) {
  return (_fetchPage: PagedFetcher<T>, search = ""): PagedListState<T> =>
    pagedListState(
      items.filter((item) =>
        displayKey(item).toLowerCase().includes(search.toLowerCase()),
      ),
      overrides,
    );
}
