import { describe, it, expect, vi, beforeEach } from "vitest";
import { http, extractErrorMessage } from "./http";

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
