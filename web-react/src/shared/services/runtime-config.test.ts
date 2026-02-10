import { describe, it, expect, vi, beforeEach } from "vitest";
import type { RuntimeConfig } from "./runtime-config";

describe("runtime-config", () => {
  const mockConfig: RuntimeConfig = {
    basePath: "/api",
    uiPath: "/",
    provider: "oidc",
    authenticated: true,
  };

  beforeEach(() => {
    vi.resetModules();
    delete window.__RUNTIME_CONFIG__;
    vi.stubGlobal("fetch", vi.fn());
  });

  it("should return cached config if available via window.__RUNTIME_CONFIG__", async () => {
    window.__RUNTIME_CONFIG__ = mockConfig;

    const module = (await import("./runtime-config?update=" + Date.now())) as {
      getRuntimeConfig: () => Promise<RuntimeConfig>;
    };

    const config = await module.getRuntimeConfig();
    expect(config).toEqual(mockConfig);
    expect(globalThis.fetch).not.toHaveBeenCalled();
  });

  it("should fetch config.json if not in window", async () => {
    delete window.__RUNTIME_CONFIG__;

    vi.mocked(globalThis.fetch).mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockConfig),
    } as Response);

    const module = (await import("./runtime-config?update=" + Date.now())) as {
      getRuntimeConfig: () => Promise<RuntimeConfig>;
    };

    const config = await module.getRuntimeConfig();
    expect(config).toEqual(mockConfig);
    expect(globalThis.fetch).toHaveBeenCalledWith(
      expect.stringContaining("config.json"),
      expect.anything(),
    );
  });

  it("should throw error if fetch fails", async () => {
    delete window.__RUNTIME_CONFIG__;

    vi.mocked(globalThis.fetch).mockResolvedValue({
      ok: false,
      status: 404,
      statusText: "Not Found",
    } as Response);

    const module = (await import("./runtime-config?update=" + Date.now())) as {
      getRuntimeConfig: () => Promise<RuntimeConfig>;
    };

    await expect(module.getRuntimeConfig()).rejects.toThrow(
      "Failed to load config.json: 404 Not Found",
    );
  });
});
