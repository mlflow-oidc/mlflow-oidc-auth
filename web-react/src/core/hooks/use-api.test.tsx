import { describe, it, expect, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { useApi } from "./use-api";
import * as useAuthModule from "./use-auth";

vi.mock("./use-auth");

describe("useApi", () => {
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
});
