
import { describe, it, expect, vi, beforeEach } from "vitest";
import { http } from "./http";

globalThis.fetch = vi.fn();

describe("http", () => {
    beforeEach(() => {
        vi.resetAllMocks();
    });

    it("performs GET request and parses JSON", async () => {
        const mockResponse = { data: "test" };
        (fetch as any).mockResolvedValue({
            ok: true,
            headers: { get: () => "application/json" },
            json: () => Promise.resolve(mockResponse),
        });

        const result = await http("/test");
        expect(result).toEqual(mockResponse);
        expect(fetch).toHaveBeenCalledWith(expect.stringContaining("/test"), expect.objectContaining({
            headers: expect.objectContaining({ "Content-Type": "application/json" }),
        }));
    });

    it("handles query params", async () => {
        (fetch as any).mockResolvedValue({
            ok: true,
            headers: { get: () => "text/plain" },
            text: () => Promise.resolve("ok"),
        });

        await http("/test", { params: { foo: "bar" } });
        expect(fetch).toHaveBeenCalledWith(expect.stringContaining("?foo=bar"), expect.anything());
    });

    it("throws on error status", async () => {
        (fetch as any).mockResolvedValue({
            ok: false,
            status: 404,
            text: () => Promise.resolve("Not Found"),
        });

        await expect(http("/test")).rejects.toThrow("HTTP 404: Not Found");
    });
});
