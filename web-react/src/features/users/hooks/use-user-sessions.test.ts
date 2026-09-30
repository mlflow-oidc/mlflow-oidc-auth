import { describe, it, expect, vi, beforeEach } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import { useUserSessions } from "./use-user-sessions";
import * as service from "../services/user-session-service";
import type { UserSession } from "../../../shared/types/user";

vi.mock("../services/user-session-service");

const session = (pk: number): UserSession => ({
  pk,
  session_id_prefix: `prefix${pk}`,
  provider_id: "default",
  created_at: "2026-09-01T00:00:00+00:00",
  last_seen_at: null,
  expires_at: "2026-09-02T00:00:00+00:00",
});

describe("useUserSessions", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("does nothing without a username", () => {
    const spy = vi.spyOn(service, "listUserSessions");
    const { result } = renderHook(() => useUserSessions(null));
    expect(spy).not.toHaveBeenCalled();
    expect(result.current.sessions).toEqual([]);
    expect(result.current.isLoading).toBe(false);
  });

  it("loads sessions and refreshes", async () => {
    const spy = vi
      .spyOn(service, "listUserSessions")
      .mockResolvedValueOnce([session(1), session(2)])
      .mockResolvedValueOnce([session(1)]);
    const { result } = renderHook(() => useUserSessions("bob@example.com"));
    await waitFor(() => expect(result.current.sessions).toHaveLength(2));
    expect(spy).toHaveBeenCalledWith("bob@example.com", expect.any(AbortSignal));

    act(() => result.current.refresh());
    await waitFor(() => expect(result.current.sessions).toHaveLength(1));
  });

  it("never shows the previous user's sessions", async () => {
    let resolveCarol: (value: UserSession[]) => void = () => undefined;
    vi.spyOn(service, "listUserSessions")
      .mockResolvedValueOnce([session(1)])
      .mockImplementationOnce(
        () => new Promise<UserSession[]>((resolve) => (resolveCarol = resolve)),
      );
    const { result, rerender } = renderHook(({ user }: { user: string }) => useUserSessions(user), {
      initialProps: { user: "bob@example.com" },
    });
    await waitFor(() => expect(result.current.sessions).toHaveLength(1));

    rerender({ user: "carol@example.com" });
    expect(result.current.sessions).toEqual([]);
    expect(result.current.isLoading).toBe(true);

    await act(async () => {
      resolveCarol([session(9)]);
      await Promise.resolve();
    });
    expect(result.current.sessions.map((s) => s.pk)).toEqual([9]);
  });

  it("reports an error", async () => {
    vi.spyOn(service, "listUserSessions").mockRejectedValue(new Error("nope"));
    const { result } = renderHook(() => useUserSessions("bob@example.com"));
    await waitFor(() => expect(result.current.error?.message).toBe("nope"));
    expect(result.current.sessions).toEqual([]);
  });
});
