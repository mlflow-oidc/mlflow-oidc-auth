import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { act, renderHook } from "@testing-library/react";
import {
  DEFAULT_PAGE_SIZE,
  PAGE_SIZE_STORAGE_KEY,
  _resetPageSizeForTests,
  parsePageSize,
  usePageSize,
} from "./use-page-size";
import { installLocalStorageMock } from "../../tests/local-storage-mock";

const storage = installLocalStorageMock();

describe("usePageSize", () => {
  beforeEach(() => {
    window.localStorage.clear();
    _resetPageSizeForTests();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    window.localStorage.clear();
    _resetPageSizeForTests();
  });

  it("defaults to 20", () => {
    const { result } = renderHook(() => usePageSize());
    expect(result.current.pageSize).toBe(20);
    expect(DEFAULT_PAGE_SIZE).toBe(20);
  });

  it("persists a new value and restores it on the next load", () => {
    const { result } = renderHook(() => usePageSize());
    act(() => result.current.setPageSize(40));
    expect(result.current.pageSize).toBe(40);
    expect(window.localStorage.getItem(PAGE_SIZE_STORAGE_KEY)).toBe("40");

    _resetPageSizeForTests();
    const { result: reloaded } = renderHook(() => usePageSize());
    expect(reloaded.current.pageSize).toBe(40);
  });

  it("stores and restores 'all'", () => {
    const { result } = renderHook(() => usePageSize());
    act(() => result.current.setPageSize("all"));
    expect(window.localStorage.getItem(PAGE_SIZE_STORAGE_KEY)).toBe("all");

    _resetPageSizeForTests();
    const { result: reloaded } = renderHook(() => usePageSize());
    expect(reloaded.current.pageSize).toBe("all");
  });

  it.each(["15", "abc", "", "-20", "20.5", "ALL"])(
    "ignores the invalid stored value %j",
    (stored) => {
      window.localStorage.setItem(PAGE_SIZE_STORAGE_KEY, stored);
      const { result } = renderHook(() => usePageSize());
      expect(result.current.pageSize).toBe(20);
    },
  );

  it("falls back to 20 without throwing when storage reads throw", () => {
    vi.spyOn(storage, "getItem").mockImplementation(() => {
      throw new Error("SecurityError");
    });
    const { result } = renderHook(() => usePageSize());
    expect(result.current.pageSize).toBe(20);
  });

  it("still applies a change in memory when storage writes throw", () => {
    vi.spyOn(storage, "setItem").mockImplementation(() => {
      throw new Error("QuotaExceededError");
    });
    const { result } = renderHook(() => usePageSize());
    expect(() => act(() => result.current.setPageSize(80))).not.toThrow();
    expect(result.current.pageSize).toBe(80);
  });

  it("keeps every mounted consumer in sync", () => {
    const first = renderHook(() => usePageSize());
    const second = renderHook(() => usePageSize());
    act(() => first.result.current.setPageSize(80));
    expect(second.result.current.pageSize).toBe(80);
  });

  it("follows a change made in another tab", () => {
    const { result } = renderHook(() => usePageSize());
    act(() => {
      window.dispatchEvent(
        new StorageEvent("storage", {
          key: PAGE_SIZE_STORAGE_KEY,
          newValue: "40",
        }),
      );
    });
    expect(result.current.pageSize).toBe(40);
  });
});

describe("parsePageSize", () => {
  it("accepts the supported options only", () => {
    expect(parsePageSize("20")).toBe(20);
    expect(parsePageSize(40)).toBe(40);
    expect(parsePageSize("80")).toBe(80);
    expect(parsePageSize("all")).toBe("all");
    expect(parsePageSize("100")).toBeNull();
    expect(parsePageSize(null)).toBeNull();
    expect(parsePageSize(undefined)).toBeNull();
  });
});
