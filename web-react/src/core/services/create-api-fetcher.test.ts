import { describe, it, expect, vi, beforeEach, type Mock } from "vitest";
import {
  createStaticApiFetcher,
  createDynamicApiFetcher,
} from "./create-api-fetcher";
import * as apiUtils from "./api-utils";

import { STATIC_API_ENDPOINTS } from "../configs/api-endpoints";

// Mock dependencies
vi.mock("./api-utils", () => ({
  request: vi.fn(),
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

      (apiUtils.request as Mock).mockResolvedValue({ data: "success" });

      const result = await fetcher();

      expect(apiUtils.request).toHaveBeenCalledWith(
        STATIC_API_ENDPOINTS.ALL_GROUPS,
        {
          method: "GET",
          signal: undefined,
          headers: { "X-Custom": "value" },
          queryParams: {}, // createStaticApiFetcher calls with default empty queryParams if not provided
        },
      );
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

      (apiUtils.request as Mock).mockResolvedValue({ data: "dynamic-success" });

      const result = await fetcher("user123", "exp456");

      const expectedPath =
        "/api/2.0/mlflow/permissions/users/user123/experiments/exp456";

      expect(apiUtils.request).toHaveBeenCalledWith(expectedPath, {
        method: "GET",
        signal: undefined,
        headers: {},
        queryParams: {}, // createDynamicApiFetcher calls with default empty queryParams if not provided
      });
      expect(result).toEqual({ data: "dynamic-success" });
    });

    it("handles signal correctly", async () => {
      const fetcher = createDynamicApiFetcher({
        endpointKey: "USER_EXPERIMENT_PERMISSION",
      });
      const signal = new AbortController().signal;
      (apiUtils.request as Mock).mockResolvedValue({ data: "success" });

      await fetcher("user1", "exp1", signal);

      expect(apiUtils.request).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          method: "GET",
          signal,
          headers: {},
          queryParams: {}, // createDynamicApiFetcher calls with default empty queryParams if not provided
        }),
      );
    });
  });
});
