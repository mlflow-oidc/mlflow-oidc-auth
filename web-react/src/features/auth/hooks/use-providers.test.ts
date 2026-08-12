import { renderHook, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, afterEach } from "vitest";

import { useProviders } from "./use-providers";

afterEach(() => {
  vi.unstubAllGlobals();
});

const ok = (body: unknown) =>
  ({ ok: true, json: () => Promise.resolve(body) }) as Response;

describe("useProviders", () => {
  it("reports the providers once they arrive", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          ok({
            providers: [
              {
                id: "entra",
                display_name: "Entra ID",
                type: "oidc",
                login_url: "/api/login/entra",
              },
            ],
          }),
        ),
      ),
    );

    const { result } = renderHook(() => useProviders("/api"));

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.providers).toHaveLength(1);
  });

  it("reports none when the fetch fails outright", async () => {
    // Network blip, or an older server. The page falls back to the login it always had rather
    // than showing an error where a sign-in button belongs.
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.reject(new Error("offline"))),
    );

    const { result } = renderHook(() => useProviders("/api"));

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.providers).toEqual([]);
  });

  it("starts out loading with nothing to show", () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise<Response>(() => {})),
    );

    const { result } = renderHook(() => useProviders("/api"));

    expect(result.current).toEqual({ providers: [], loading: true });
  });
});
