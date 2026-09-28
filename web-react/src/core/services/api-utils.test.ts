import { describe, it, expect, vi } from "vitest";
import { resolveUrl, requestWithStatus } from "./api-utils";
import * as runtimeConfig from "../../shared/services/runtime-config";
import type { RuntimeConfig } from "../../shared/services/runtime-config";
import * as http from "./http";

vi.mock("./http", async () => {
  const actual = await vi.importActual<typeof import("./http")>("./http");
  return { ...actual, httpWithStatus: vi.fn() };
});

describe("api-utils", () => {
  it("resolveUrl builds correct URL with params", async () => {
    const mockConfig: RuntimeConfig = {
      basePath: "/api/v1",
      uiPath: "/ui",
      provider: "oidc",
      authenticated: true,
      gen_ai_gateway_enabled: false,
      workspaces_enabled: false,
    };
    vi.spyOn(runtimeConfig, "getRuntimeConfig").mockResolvedValue(mockConfig);

    const url = await resolveUrl("/users", { limit: 10, offset: 0 });
    expect(url).toBe("/api/v1/users?limit=10&offset=0");
  });

  it("resolveUrl handles unknown params", async () => {
    const mockConfig: RuntimeConfig = {
      basePath: "/api/v1",
      uiPath: "/ui",
      provider: "oidc",
      authenticated: true,
      gen_ai_gateway_enabled: false,
      workspaces_enabled: false,
    };
    vi.spyOn(runtimeConfig, "getRuntimeConfig").mockResolvedValue(mockConfig);

    const url = await resolveUrl("/users", {
      valid: true,
      invalid: undefined,
      nullVal: null,
    });
    expect(url).toBe("/api/v1/users?valid=true");
  });

  it("requestWithStatus resolves the URL and returns the status alongside the body", async () => {
    const mockConfig: RuntimeConfig = {
      basePath: "/api/v1",
      uiPath: "/ui",
      provider: "oidc",
      authenticated: true,
      gen_ai_gateway_enabled: false,
      workspaces_enabled: false,
    };
    vi.spyOn(runtimeConfig, "getRuntimeConfig").mockResolvedValue(mockConfig);
    vi.mocked(http.httpWithStatus).mockResolvedValue({
      data: { message: "created" },
      status: 201,
    });

    const result = await requestWithStatus("/groups", { method: "POST" });

    expect(http.httpWithStatus).toHaveBeenCalledWith(
      "/api/v1/groups",
      expect.objectContaining({ method: "POST" }),
    );
    expect(result).toEqual({ data: { message: "created" }, status: 201 });
  });
});
