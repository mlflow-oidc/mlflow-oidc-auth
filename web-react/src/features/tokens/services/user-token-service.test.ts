import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  createUserToken,
  deleteUserToken,
  listUserTokens,
  revokeAllUserTokens,
} from "./user-token-service";
import * as apiUtils from "../../../core/services/api-utils";

vi.mock("../../../core/services/api-utils", () => ({
  request: vi.fn(),
}));

const request = vi.mocked(apiUtils.request);

describe("user-token-service", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("lists the signed-in user's tokens", async () => {
    request.mockResolvedValue({ tokens: [{ id: 1 }] });
    await expect(listUserTokens(undefined)).resolves.toEqual([{ id: 1 }]);
    expect(request).toHaveBeenCalledWith("/api/2.0/mlflow/users/tokens", {
      signal: undefined,
    });
  });

  it("lists another user's tokens with the username encoded", async () => {
    request.mockResolvedValue({});
    await expect(listUserTokens("a/b@x.com")).resolves.toEqual([]);
    expect(request).toHaveBeenCalledWith(
      "/api/2.0/mlflow/users/a%2Fb%40x.com/tokens",
      { signal: undefined },
    );
  });

  it("creates a token with name and expiration", async () => {
    const data = { name: "ci", expiration: "2027-01-01T23:59:59Z" };
    await createUserToken(undefined, data);
    expect(request).toHaveBeenCalledWith("/api/2.0/mlflow/users/tokens", {
      method: "POST",
      body: JSON.stringify(data),
    });
    await createUserToken("bob", data);
    expect(request).toHaveBeenLastCalledWith(
      "/api/2.0/mlflow/users/bob/tokens",
      { method: "POST", body: JSON.stringify(data) },
    );
  });

  it("deletes one token", async () => {
    await deleteUserToken(undefined, 7);
    expect(request).toHaveBeenCalledWith("/api/2.0/mlflow/users/tokens/7", {
      method: "DELETE",
    });
    await deleteUserToken("bob smith", 8);
    expect(request).toHaveBeenLastCalledWith(
      "/api/2.0/mlflow/users/bob%20smith/tokens/8",
      { method: "DELETE" },
    );
  });

  it("revokes all of a user's tokens", async () => {
    request.mockResolvedValue({ revoked: 3 });
    await expect(revokeAllUserTokens("bob")).resolves.toEqual({ revoked: 3 });
    expect(request).toHaveBeenCalledWith("/api/2.0/mlflow/users/bob/tokens", {
      method: "DELETE",
    });
  });
});
