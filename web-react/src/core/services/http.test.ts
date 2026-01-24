import { describe, it, expect, vi, beforeEach } from "vitest";
import { http } from "./http";

globalThis.fetch = vi.fn<typeof fetch>();

describe("http", () => {
  beforeEach(() => {
    vi.resetAllMocks();
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
});
