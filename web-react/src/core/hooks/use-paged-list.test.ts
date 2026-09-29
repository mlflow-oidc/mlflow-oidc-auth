import { describe, it, expect, vi, beforeEach } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import { usePagedList } from "./use-paged-list";
import { _resetPageSizeForTests, usePageSize } from "./use-page-size";
import * as useAuthModule from "./use-auth";
import * as workspaceContext from "../../shared/context/use-workspace";
import type { PagedFetcher } from "../services/paged-list";
import { installLocalStorageMock } from "../../tests/local-storage-mock";

vi.mock("./use-auth");
vi.mock("../../shared/context/use-workspace");

installLocalStorageMock();

describe("usePagedList", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    _resetPageSizeForTests();
    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      isAuthenticated: true,
    } as ReturnType<typeof useAuthModule.useAuth>);
    vi.spyOn(workspaceContext, "useSelectedWorkspace").mockReturnValue(null);
  });

  const makeFetcher = (total: number) =>
    vi.fn<PagedFetcher<number>>((query) => {
      const all = Array.from({ length: total }, (_, i) => i + 1);
      const offset = query.offset ?? 0;
      const page =
        query.limit === undefined
          ? all
          : all.slice(offset, offset + query.limit);
      return Promise.resolve({ items: page, total });
    });

  it("requests the first page with the default size", async () => {
    const fetcher = makeFetcher(50);
    const { result } = renderHook(() => usePagedList(fetcher));
    await waitFor(() => expect(result.current.items).toHaveLength(20));
    expect(fetcher).toHaveBeenLastCalledWith(
      { limit: 20, offset: 0, search: "" },
      expect.any(AbortSignal),
    );
    expect(result.current.total).toBe(50);
    expect(result.current.pagination).toMatchObject({
      total: 50,
      page: 1,
      pageSize: 20,
    });
  });

  it("requests the offset for another page and keeps rows while fetching", async () => {
    const fetcher = makeFetcher(50);
    const { result } = renderHook(() => usePagedList(fetcher));
    await waitFor(() => expect(result.current.items).toHaveLength(20));

    act(() => result.current.pagination.onPageChange(3));
    expect(result.current.isLoading).toBe(false);
    await waitFor(() =>
      expect(result.current.items).toEqual([
        41, 42, 43, 44, 45, 46, 47, 48, 49, 50,
      ]),
    );
    expect(fetcher).toHaveBeenLastCalledWith(
      { limit: 20, offset: 40, search: "" },
      expect.any(AbortSignal),
    );
  });

  it("sends the search and goes back to page 1 when it changes", async () => {
    const fetcher = makeFetcher(50);
    const { result, rerender } = renderHook(
      ({ search }) => usePagedList(fetcher, search),
      { initialProps: { search: "" } },
    );
    await waitFor(() => expect(result.current.items).toHaveLength(20));
    act(() => result.current.setPage(2));
    await waitFor(() => expect(result.current.page).toBe(2));

    rerender({ search: "abc" });
    expect(result.current.page).toBe(1);
    await waitFor(() =>
      expect(fetcher).toHaveBeenLastCalledWith(
        { limit: 20, offset: 0, search: "abc" },
        expect.any(AbortSignal),
      ),
    );
  });

  it("omits limit for All and resets to page 1 on a size change", async () => {
    const fetcher = makeFetcher(50);
    const { result } = renderHook(() => ({
      list: usePagedList(fetcher),
      size: usePageSize(),
    }));
    await waitFor(() => expect(result.current.list.items).toHaveLength(20));
    act(() => result.current.list.setPage(2));

    act(() => result.current.size.setPageSize("all"));
    expect(result.current.list.page).toBe(1);
    await waitFor(() => expect(result.current.list.items).toHaveLength(50));
    expect(fetcher).toHaveBeenLastCalledWith(
      { limit: undefined, offset: undefined, search: "" },
      expect.any(AbortSignal),
    );
  });

  it("moves to the last page when the current one comes back empty", async () => {
    let total = 50;
    const fetcher = vi.fn<PagedFetcher<number>>((query) => {
      const all = Array.from({ length: total }, (_, i) => i + 1);
      const offset = query.offset ?? 0;
      return Promise.resolve({
        items: all.slice(offset, offset + (query.limit ?? total)),
        total,
      });
    });
    const { result } = renderHook(() => usePagedList(fetcher));
    await waitFor(() => expect(result.current.items).toHaveLength(20));
    act(() => result.current.setPage(3));
    await waitFor(() => expect(result.current.items).toHaveLength(10));

    // Rows on the last page get deleted elsewhere, then the list is refreshed.
    total = 40;
    act(() => result.current.refresh());
    await waitFor(() => expect(result.current.page).toBe(2));
    await waitFor(() => expect(result.current.items).toHaveLength(20));
  });
});
