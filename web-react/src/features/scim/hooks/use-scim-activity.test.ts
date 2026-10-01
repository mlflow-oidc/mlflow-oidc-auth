import { describe, it, expect, vi, beforeEach } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import { useScimActivity, SCIM_ACTIVITY_PAGE_SIZE } from "./use-scim-activity";
import * as service from "../services/scim-activity-service";
import * as useAuthModule from "../../../core/hooks/use-auth";
import type { UseAuthResult } from "../../../core/hooks/use-auth";
import type {
  ScimActivityEntry,
  ScimActivityOutcome,
} from "../../../shared/types/scim";

vi.mock("../services/scim-activity-service");
vi.mock("../../../core/hooks/use-auth");

function entry(id: number, outcome: ScimActivityEntry["outcome"] = "ok"): ScimActivityEntry {
  return {
    id,
    at: "2026-09-01T00:00:00+00:00",
    token_id: 1,
    token_name: "entra",
    method: "GET",
    path: "/Users",
    resource_id: null,
    status: outcome === "ok" ? 200 : 409,
    outcome,
    error: outcome === "ok" ? null : "uniqueness: taken",
    duration_ms: 3,
  };
}

describe("useScimActivity", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      isAuthenticated: true,
    } as UseAuthResult);
  });

  it("loads the first page and then appends the next one", async () => {
    const fetchSpy = vi
      .spyOn(service, "fetchScimActivity")
      .mockResolvedValueOnce({ activity: [entry(5), entry(4)], next_before: 4 })
      .mockResolvedValueOnce({ activity: [entry(3)], next_before: null });

    const { result } = renderHook(() => useScimActivity(null));
    await waitFor(() => {
      expect(result.current.entries.map((e) => e.id)).toEqual([5, 4]);
      expect(result.current.hasMore).toBe(true);
    });
    expect(fetchSpy).toHaveBeenNthCalledWith(
      1,
      { limit: SCIM_ACTIVITY_PAGE_SIZE, outcome: undefined },
      expect.any(AbortSignal),
    );

    await act(async () => {
      await result.current.loadMore();
    });

    expect(fetchSpy).toHaveBeenNthCalledWith(2, {
      limit: SCIM_ACTIVITY_PAGE_SIZE,
      before: 4,
      outcome: undefined,
    });
    expect(result.current.entries.map((e) => e.id)).toEqual([5, 4, 3]);
    expect(result.current.hasMore).toBe(false);
  });

  it("restarts from the newest row when the filter changes", async () => {
    const fetchSpy = vi
      .spyOn(service, "fetchScimActivity")
      .mockResolvedValueOnce({ activity: [entry(2), entry(1)], next_before: null })
      .mockResolvedValueOnce({ activity: [entry(1, "client_error")], next_before: null });

    const { result, rerender } = renderHook(
      ({ outcome }: { outcome: ScimActivityOutcome | null }) => useScimActivity(outcome),
      { initialProps: { outcome: null as ScimActivityOutcome | null } },
    );
    await waitFor(() => expect(result.current.entries).toHaveLength(2));

    rerender({ outcome: "client_error" });
    await waitFor(() => {
      expect(result.current.entries.map((e) => e.outcome)).toEqual(["client_error"]);
    });
    expect(fetchSpy).toHaveBeenLastCalledWith(
      { limit: SCIM_ACTIVITY_PAGE_SIZE, outcome: "client_error" },
      expect.any(AbortSignal),
    );
  });

  it("never appends a page fetched with the previous filter's cursor", async () => {
    let resolveFiltered: (page: { activity: ScimActivityEntry[]; next_before: number | null }) => void = () => undefined;
    const fetchSpy = vi
      .spyOn(service, "fetchScimActivity")
      .mockResolvedValueOnce({ activity: [entry(5), entry(4)], next_before: 4 })
      .mockImplementationOnce(() => new Promise((resolve) => (resolveFiltered = resolve)))
      .mockResolvedValue({ activity: [entry(3)], next_before: null });

    const { result, rerender } = renderHook(
      ({ outcome }: { outcome: ScimActivityOutcome | null }) => useScimActivity(outcome),
      { initialProps: { outcome: null as ScimActivityOutcome | null } },
    );
    await waitFor(() => expect(result.current.hasMore).toBe(true));
    const staleLoadMore = result.current.loadMore;

    // Switch the filter; its first page is still in flight.
    rerender({ outcome: "client_error" });
    expect(result.current.isLoading).toBe(true);
    expect(result.current.hasMore).toBe(false);

    // Both the stale callback and the current one must do nothing yet.
    await act(async () => {
      await staleLoadMore();
      await result.current.loadMore();
    });
    expect(fetchSpy).toHaveBeenCalledTimes(2);

    await act(async () => {
      resolveFiltered({ activity: [entry(9, "client_error")], next_before: null });
      await Promise.resolve();
    });
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.entries.map((e) => e.id)).toEqual([9]);
    expect(fetchSpy).not.toHaveBeenCalledWith(expect.objectContaining({ before: 4 }));
  });

  it("reports an error and refresh fetches again", async () => {
    const fetchSpy = vi
      .spyOn(service, "fetchScimActivity")
      .mockRejectedValueOnce(new Error("down"))
      .mockResolvedValueOnce({ activity: [entry(1)], next_before: null });

    const { result } = renderHook(() => useScimActivity(null));
    await waitFor(() => expect(result.current.error?.message).toBe("down"));

    act(() => result.current.refresh());
    await waitFor(() => {
      expect(result.current.error).toBeNull();
      expect(result.current.entries).toHaveLength(1);
    });
    expect(fetchSpy).toHaveBeenCalledTimes(2);
  });

  it("does not fetch when unauthenticated", () => {
    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      isAuthenticated: false,
    } as UseAuthResult);
    const fetchSpy = vi.spyOn(service, "fetchScimActivity");
    renderHook(() => useScimActivity(null));
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});
