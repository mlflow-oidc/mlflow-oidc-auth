import { describe, it, expect, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { useApi } from "./use-api";
import * as useAuthModule from "./use-auth";
import * as useWorkspaceModule from "../../shared/context/use-workspace";

vi.mock("./use-auth");
vi.mock("../../shared/context/use-workspace");

describe("useApi", () => {
  beforeEach(() => {
    vi.spyOn(useWorkspaceModule, "useSelectedWorkspace").mockReturnValue(null);
  });

  it("does not fetch when not authenticated", () => {
    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      isAuthenticated: false,
    });
    const fetcher = vi.fn();
    const { result } = renderHook(() => useApi(fetcher));

    expect(fetcher).not.toHaveBeenCalled();
    expect(result.current.data).toBeNull();
    expect(result.current.isLoading).toBe(false);
  });

  it("fetches data when authenticated", async () => {
    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      isAuthenticated: true,
    });
    const mockData = { id: 1, name: "Test" };
    const fetcher = vi.fn().mockResolvedValue(mockData);

    const { result } = renderHook(() => useApi(fetcher));

    await waitFor(() => {
      expect(result.current.data).toEqual(mockData);
    });
    expect(fetcher).toHaveBeenCalled();
  });

  it("handles errors", async () => {
    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      isAuthenticated: true,
    });
    const fetcher = vi.fn().mockRejectedValue(new Error("API Error"));

    const { result } = renderHook(() => useApi(fetcher));

    await waitFor(() => {
      expect(result.current.error).toBeTruthy();
      expect(result.current.error?.message).toBe("API Error");
    });
  });

  it("ignores a refetch that resolves after a newer request", async () => {
    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      isAuthenticated: true,
    });
    let resolveSlow: (value: string) => void = () => {};
    const pageOne = vi
      .fn()
      .mockResolvedValueOnce("page 1")
      .mockImplementationOnce(
        () => new Promise<string>((resolve) => (resolveSlow = resolve)),
      );
    const pageTwo = vi.fn().mockResolvedValue("page 2");

    const { result, rerender } = renderHook(
      ({ fetcher }) => useApi<string>(fetcher),
      { initialProps: { fetcher: pageOne } },
    );
    await waitFor(() => expect(result.current.data).toBe("page 1"));

    // Refresh page 1 (slow), then move to page 2 before it answers.
    result.current.refetch();
    rerender({ fetcher: pageTwo });
    await waitFor(() => expect(result.current.data).toBe("page 2"));

    resolveSlow("page 1 (late)");
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(result.current.data).toBe("page 2");
    expect(result.current.isLoading).toBe(false);
  });

  it("reports data from the previous fetcher as stale", async () => {
    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      isAuthenticated: true,
    });
    const first = vi.fn().mockResolvedValue("first");
    const second = vi.fn(() => new Promise<string>(() => {}));

    const { result, rerender } = renderHook(
      ({ fetcher }) => useApi<string>(fetcher),
      { initialProps: { fetcher: first as () => Promise<string> } },
    );
    await waitFor(() => expect(result.current.data).toBe("first"));
    expect(result.current.isStale).toBe(false);

    rerender({ fetcher: second });
    expect(result.current.data).toBe("first");
    expect(result.current.isStale).toBe(true);
  });

  it("reports data from the previous workspace as stale", async () => {
    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      isAuthenticated: true,
    });
    const workspaceSpy = vi
      .spyOn(useWorkspaceModule, "useSelectedWorkspace")
      .mockReturnValue("ws1");
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce("ws1 data")
      .mockImplementationOnce(() => new Promise<string>(() => {}));

    const { result, rerender } = renderHook(() => useApi<string>(fetcher));
    await waitFor(() => expect(result.current.data).toBe("ws1 data"));
    expect(result.current.isStale).toBe(false);

    // Same fetcher, new workspace: the data still belongs to ws1.
    workspaceSpy.mockReturnValue("ws2");
    rerender();
    expect(result.current.data).toBe("ws1 data");
    expect(result.current.isStale).toBe(true);
  });

  it("re-fetches when workspace changes", async () => {
    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      isAuthenticated: true,
    });

    let currentWorkspace: string | null = null;
    const workspaceSpy = vi
      .spyOn(useWorkspaceModule, "useSelectedWorkspace")
      .mockImplementation(() => currentWorkspace);

    const dataA = { workspace: "all" };
    const dataB = { workspace: "ws1" };
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(dataA)
      .mockResolvedValueOnce(dataB);

    const { result, rerender } = renderHook(() => useApi(fetcher));

    // Initial fetch with null workspace
    await waitFor(() => {
      expect(result.current.data).toEqual(dataA);
    });
    expect(fetcher).toHaveBeenCalledTimes(1);

    // Change workspace — should trigger re-fetch
    currentWorkspace = "ws1";
    workspaceSpy.mockReturnValue("ws1");
    rerender();

    await waitFor(() => {
      expect(result.current.data).toEqual(dataB);
    });
    expect(fetcher).toHaveBeenCalledTimes(2);
  });
});
