import { describe, it, expect, vi, beforeEach } from "vitest";
import { http, extractErrorMessage, _resetReauthForTests } from "./http";

vi.mock("../../shared/context/workspace-context", () => ({
  getActiveWorkspace: vi.fn(() => null),
}));

import { getActiveWorkspace } from "../../shared/context/workspace-context";

globalThis.fetch = vi.fn<typeof fetch>();

describe("http", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(getActiveWorkspace).mockReturnValue(null);
  });

  it("performs GET request and parses JSON", async () => {
    const mockResponse = { data: "test" };
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      status: 200,
      statusText: "OK",
      headers: new Headers({ "content-type": "application/json" }),
      json: () => Promise.resolve(mockResponse),
      text: () => Promise.resolve(JSON.stringify(mockResponse)),
    } as Response);

    const result = await http("/test");
    expect(result).toEqual(mockResponse);
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining("/test"),
      expect.objectContaining({
        headers: { "Content-Type": "application/json" },
      }),
    );
  });

  it("handles query params", async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      status: 200,
      statusText: "OK",
      headers: new Headers({ "content-type": "text/plain" }),
      text: () => Promise.resolve("ok"),
    } as Response);

    await http("/test", { params: { foo: "bar" } });
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining("?foo=bar"),
      expect.anything(),
    );
  });

  it("throws on error status", async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: false,
      status: 404,
      statusText: "Not Found",
      headers: new Headers(),
      text: () => Promise.resolve("Not Found"),
    } as Response);

    await expect(http("/test")).rejects.toThrow("HTTP 404: Not Found");
  });

  it("sends X-MLFLOW-WORKSPACE header when workspace is active", async () => {
    vi.mocked(getActiveWorkspace).mockReturnValue("my-workspace");

    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      status: 200,
      statusText: "OK",
      headers: new Headers({ "content-type": "application/json" }),
      json: () => Promise.resolve({}),
      text: () => Promise.resolve("{}"),
    } as Response);

    await http("/test");
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining("/test"),
      expect.objectContaining({
        headers: {
          "Content-Type": "application/json",
          "X-MLFLOW-WORKSPACE": "my-workspace",
        },
      }),
    );
  });

  it("does not send X-MLFLOW-WORKSPACE header when workspace is null", async () => {
    vi.mocked(getActiveWorkspace).mockReturnValue(null);

    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      status: 200,
      statusText: "OK",
      headers: new Headers({ "content-type": "application/json" }),
      json: () => Promise.resolve({}),
      text: () => Promise.resolve("{}"),
    } as Response);

    await http("/test");
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining("/test"),
      expect.objectContaining({
        headers: { "Content-Type": "application/json" },
      }),
    );
  });

  it("includes credentials in all requests", async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      status: 200,
      statusText: "OK",
      headers: new Headers({ "content-type": "text/plain" }),
      text: () => Promise.resolve("ok"),
    } as Response);

    await http("/test");
    expect(fetch).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({
        credentials: "include",
      }),
    );
  });

  describe("401 reauth redirect", () => {
    let assignSpy: ReturnType<typeof vi.fn>;
    let originalLocation: Location;

    beforeEach(() => {
      _resetReauthForTests();
      assignSpy = vi.fn();
      // jsdom won't let us reassign window.location, so swap a stub in.
      originalLocation = window.location;
      Object.defineProperty(window, "location", {
        configurable: true,
        value: {
          ...originalLocation,
          pathname: "/oidc/ui/users",
          search: "",
          hash: "",
          assign: assignSpy,
        },
      });
      // Reset runtime config between tests.
      delete (window as { __RUNTIME_CONFIG__?: unknown }).__RUNTIME_CONFIG__;
    });

    afterEachRestoreLocation: {
      // jsdom limitation: the location stub is replaced per-test in beforeEach,
      // so explicit restore isn't required.
    }

    it("redirects to /login with ?next= on 401 from a non-auth page", async () => {
      vi.mocked(fetch).mockResolvedValue({
        ok: false,
        status: 401,
        statusText: "Unauthorized",
        headers: new Headers(),
        text: () => Promise.resolve("expired"),
      } as Response);

      await expect(http("/api/users")).rejects.toThrow("HTTP 401");
      expect(assignSpy).toHaveBeenCalledTimes(1);
      expect(assignSpy).toHaveBeenCalledWith(
        "/login?next=" + encodeURIComponent("/oidc/ui/users"),
      );
    });

    it("preserves search and hash in ?next=", async () => {
      Object.defineProperty(window, "location", {
        configurable: true,
        value: {
          ...window.location,
          pathname: "/",
          search: "?tab=runs",
          hash: "#/experiments/0",
          assign: assignSpy,
        },
      });

      vi.mocked(fetch).mockResolvedValue({
        ok: false,
        status: 401,
        statusText: "Unauthorized",
        headers: new Headers(),
        text: () => Promise.resolve("expired"),
      } as Response);

      await expect(http("/api/users")).rejects.toThrow("HTTP 401");
      expect(assignSpy).toHaveBeenCalledWith(
        "/login?next=" + encodeURIComponent("/?tab=runs#/experiments/0"),
      );
    });

    it("does not redirect when already on the auth feature page", async () => {
      Object.defineProperty(window, "location", {
        configurable: true,
        value: {
          ...window.location,
          pathname: "/oidc/ui/auth",
          search: "",
          hash: "",
          assign: assignSpy,
        },
      });

      vi.mocked(fetch).mockResolvedValue({
        ok: false,
        status: 401,
        statusText: "Unauthorized",
        headers: new Headers(),
        text: () => Promise.resolve("expired"),
      } as Response);

      await expect(http("/api/users")).rejects.toThrow("HTTP 401");
      expect(assignSpy).not.toHaveBeenCalled();
    });

    it("redirects only once for concurrent 401s", async () => {
      vi.mocked(fetch).mockResolvedValue({
        ok: false,
        status: 401,
        statusText: "Unauthorized",
        headers: new Headers(),
        text: () => Promise.resolve("expired"),
      } as Response);

      await Promise.allSettled([http("/a"), http("/b"), http("/c")]);
      expect(assignSpy).toHaveBeenCalledTimes(1);
    });

    it("uses runtime config basePath for the login URL behind a proxy", async () => {
      (window as { __RUNTIME_CONFIG__?: { basePath?: string } }).__RUNTIME_CONFIG__ = {
        basePath: "/proxy/path",
      };

      vi.mocked(fetch).mockResolvedValue({
        ok: false,
        status: 401,
        statusText: "Unauthorized",
        headers: new Headers(),
        text: () => Promise.resolve("expired"),
      } as Response);

      await expect(http("/api/users")).rejects.toThrow("HTTP 401");
      expect(assignSpy).toHaveBeenCalledWith(
        "/proxy/path/login?next=" + encodeURIComponent("/oidc/ui/users"),
      );
    });

    it("ignores <base href> (which points at /oidc/ui/) when redirecting", async () => {
      // The plugin SPA's <base href> is the UI mount point — not the right
      // anchor for /login, which lives at <basePath>/login.
      const baseEl = document.createElement("base");
      baseEl.setAttribute("href", "/oidc/ui/");
      document.head.appendChild(baseEl);

      vi.mocked(fetch).mockResolvedValue({
        ok: false,
        status: 401,
        statusText: "Unauthorized",
        headers: new Headers(),
        text: () => Promise.resolve("expired"),
      } as Response);

      await expect(http("/api/users")).rejects.toThrow("HTTP 401");
      // Falls back to root because no runtime config is set, so /login (NOT
      // /oidc/ui/login) is what gets called.
      expect(assignSpy).toHaveBeenCalledWith(
        "/login?next=" + encodeURIComponent("/oidc/ui/users"),
      );

      baseEl.remove();
    });

    it("does not redirect on non-401 errors", async () => {
      vi.mocked(fetch).mockResolvedValue({
        ok: false,
        status: 500,
        statusText: "Internal Server Error",
        headers: new Headers(),
        text: () => Promise.resolve("boom"),
      } as Response);

      await expect(http("/api/users")).rejects.toThrow("HTTP 500");
      expect(assignSpy).not.toHaveBeenCalled();
    });
  });

  it("returns undefined for 204 No Content responses", async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      status: 204,
      statusText: "No Content",
      headers: new Headers({ "content-type": "application/json" }),
      json: () => Promise.reject(new Error("Unexpected end of JSON input")),
      text: () => Promise.resolve(""),
    } as Response);

    const result = await http("/test");
    expect(result).toBeUndefined();
  });
});

describe("extractErrorMessage", () => {
  it("extracts message from JSON error body", () => {
    const error = new Error(
      'HTTP 400: {"error_code":"INVALID_STATE","message":"Pattern exceeds maximum length","details":null}',
    );
    expect(extractErrorMessage(error, "fallback")).toBe(
      "Pattern exceeds maximum length",
    );
  });

  it("returns raw text when body is not JSON", () => {
    const error = new Error("HTTP 500: Internal Server Error");
    expect(extractErrorMessage(error, "fallback")).toBe(
      "Internal Server Error",
    );
  });

  it("returns fallback for non-Error objects", () => {
    expect(extractErrorMessage("string error", "fallback")).toBe("fallback");
  });

  it("returns fallback when error message does not match HTTP pattern", () => {
    const error = new Error("Network failure");
    expect(extractErrorMessage(error, "fallback")).toBe("fallback");
  });

  it("returns fallback when JSON body has no message field", () => {
    const error = new Error('HTTP 400: {"error_code":"INVALID_STATE"}');
    expect(extractErrorMessage(error, "fallback")).toBe("fallback");
  });
});
