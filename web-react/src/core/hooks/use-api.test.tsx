import { describe, it, expect, vi } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
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
