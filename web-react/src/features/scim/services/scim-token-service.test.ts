import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  listScimTokens,
  createScimToken,
  rotateScimToken,
  revokeScimToken,
} from "./scim-token-service";
import * as apiUtils from "../../../core/services/api-utils";
import { STATIC_API_ENDPOINTS } from "../../../core/configs/api-endpoints";

vi.mock("../../../core/services/api-utils", () => ({
  request: vi.fn(),
}));

describe("scim-token-service", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("listScimTokens calls request with the tokens resource", async () => {
    await listScimTokens();
    expect(apiUtils.request).toHaveBeenCalledWith(
      STATIC_API_ENDPOINTS.SCIM_TOKENS_RESOURCE,
      expect.objectContaining({
        method: "GET",
      }),
    );
  });

  it("createScimToken calls request with POST and body", async () => {
    const data = { name: "Entra ID", expires_at: "2027-01-01T00:00:00Z" };
    await createScimToken(data);
    expect(apiUtils.request).toHaveBeenCalledWith(
      STATIC_API_ENDPOINTS.SCIM_TOKENS_RESOURCE,
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify(data),
      }),
    );
  });

  it("createScimToken works without an expiry", async () => {
    const data = { name: "Entra ID" };
    await createScimToken(data);
    expect(apiUtils.request).toHaveBeenCalledWith(
      STATIC_API_ENDPOINTS.SCIM_TOKENS_RESOURCE,
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify(data),
      }),
    );
  });

  it("rotateScimToken calls request with POST against the rotate endpoint", async () => {
    await rotateScimToken(42);
    expect(apiUtils.request).toHaveBeenCalledWith(
      expect.stringContaining("/api/2.0/mlflow/scim/tokens/42/rotate"),
      expect.objectContaining({
        method: "POST",
      }),
    );
  });

  it("revokeScimToken calls request with DELETE against the token endpoint", async () => {
    await revokeScimToken(42);
    expect(apiUtils.request).toHaveBeenCalledWith(
      expect.stringContaining("/api/2.0/mlflow/scim/tokens/42"),
      expect.objectContaining({
        method: "DELETE",
      }),
    );
  });
});
