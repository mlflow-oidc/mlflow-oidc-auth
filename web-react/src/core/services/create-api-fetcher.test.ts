import { describe, it, expect, vi, beforeEach, type Mock } from "vitest";
import {
  createStaticApiFetcher,
  createDynamicApiFetcher,
} from "./create-api-fetcher";
import { http } from "./http";
import * as apiUtils from "./api-utils";

import { STATIC_API_ENDPOINTS } from "../configs/api-endpoints";

// Mock dependencies
vi.mock("./http", () => ({
  http: vi.fn(),
}));

vi.mock("./api-utils", () => ({
  resolveUrl: vi.fn(),
}));

describe("create-api-fetcher", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("createStaticApiFetcher", () => {
    it("createStaticApiFetcher returns a function", () => {
      const fetcher = createStaticApiFetcher({
        endpointKey: "ALL_GROUPS",
      });
      expect(typeof fetcher).toBe("function");
    });

    it("fetches data with correct arguments", async () => {
      const fetcher = createStaticApiFetcher({
        endpointKey: "ALL_GROUPS",
        headers: { "X-Custom": "value" },
      });

      const mockUrl = "resolved-url";
      (apiUtils.resolveUrl as Mock).mockResolvedValue(mockUrl);
      (http as Mock).mockResolvedValue({ data: "success" });

      const result = await fetcher();

      expect(apiUtils.resolveUrl).toHaveBeenCalledWith(
        STATIC_API_ENDPOINTS.ALL_GROUPS,
        {},
        undefined,
      );
      expect(http).toHaveBeenCalledWith(mockUrl, {
        method: "GET",
        signal: undefined,
        headers: { "X-Custom": "value" },
      });
      expect(result).toEqual({ data: "success" });
    });
  });

  describe("createDynamicApiFetcher", () => {
    it("createDynamicApiFetcher returns a function", () => {
      const fetcher = createDynamicApiFetcher({
        endpointKey: "USER_EXPERIMENT_PERMISSION",
      });
      expect(typeof fetcher).toBe("function");
    });

    it("fetches data utilizing dynamic arguments", async () => {
      const fetcher = createDynamicApiFetcher({
        endpointKey: "USER_EXPERIMENT_PERMISSION",
      });

      const mockUrl = "resolved-dynamic-url";
      (apiUtils.resolveUrl as Mock).mockResolvedValue(mockUrl);
      (http as Mock).mockResolvedValue({ data: "dynamic-success" });

      const result = await fetcher("user123", "exp456");

      const expectedPath =
        "/api/2.0/mlflow/permissions/users/user123/experiments/exp456";

      expect(apiUtils.resolveUrl).toHaveBeenCalledWith(
        expectedPath,
        {},
        undefined,
      );
      expect(http).toHaveBeenCalledWith(mockUrl, {
        method: "GET",
        signal: undefined,
        headers: {},
      });
      expect(result).toEqual({ data: "dynamic-success" });
    });

    it("handles signal correctly", async () => {
      const fetcher = createDynamicApiFetcher({
        endpointKey: "USER_EXPERIMENT_PERMISSION",
      });
      const signal = new AbortController().signal;
      const mockUrl = "url-with-signal";
      (apiUtils.resolveUrl as Mock).mockResolvedValue(mockUrl);

      await fetcher("user1", "exp1", signal);

      expect(apiUtils.resolveUrl).toHaveBeenCalledWith(
        expect.any(String),
        {},
        signal,
      );
      expect(http).toHaveBeenCalledWith(
        mockUrl,
        expect.objectContaining({
          signal,
        }),
      );
    });
  });
});
