import { describe, it, expect, vi, beforeEach } from "vitest";
import { fetchScimActivity, fetchScimStatus } from "./scim-activity-service";
import * as apiUtils from "../../../core/services/api-utils";
import { STATIC_API_ENDPOINTS } from "../../../core/configs/api-endpoints";

vi.mock("../../../core/services/api-utils", () => ({
  request: vi.fn(),
}));

describe("scim-activity-service", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("fetchScimStatus GETs the status endpoint", async () => {
    await fetchScimStatus();
    expect(apiUtils.request).toHaveBeenCalledWith(
      STATIC_API_ENDPOINTS.SCIM_STATUS,
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("fetchScimActivity passes paging and filters as query params", async () => {
    await fetchScimActivity({ limit: 50, before: 10, outcome: "client_error" });
    expect(apiUtils.request).toHaveBeenCalledWith(
      STATIC_API_ENDPOINTS.SCIM_ACTIVITY,
      expect.objectContaining({
        method: "GET",
        queryParams: {
          limit: 50,
          before: 10,
          outcome: "client_error",
          token_id: undefined,
        },
      }),
    );
  });

  it("fetchScimActivity works without a query", async () => {
    await fetchScimActivity();
    expect(apiUtils.request).toHaveBeenCalledWith(
      STATIC_API_ENDPOINTS.SCIM_ACTIVITY,
      expect.objectContaining({ method: "GET" }),
    );
  });
});
