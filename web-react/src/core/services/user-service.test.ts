import { describe, it, expect, vi } from "vitest";
import {
  createUser,
  deleteUser,
  fetchAllUserDetails,
  setUserActive,
} from "./user-service";
import { http } from "./http";
import { getRuntimeConfig } from "../../shared/services/runtime-config";

vi.mock("./http");
vi.mock("../../shared/services/runtime-config", () => ({
  getRuntimeConfig: vi.fn(() =>
    Promise.resolve({
      basePath: "",
      uiPath: "",
      provider: "",
      authenticated: true,
    }),
  ),
}));

describe("user-service", () => {
  it("createUser sends POST request", async () => {
    const userData = {
      username: "test",
      display_name: "Test",
      is_admin: false,
      is_service_account: false,
    };
    await createUser(userData);
    expect(http).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify(userData),
      }),
    );
  });

  it("deleteUser sends DELETE request", async () => {
    await deleteUser("testuser");
    expect(http).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        method: "DELETE",
        body: JSON.stringify({ username: "testuser" }),
      }),
    );
  });

  it("prefixes URL with basePath from runtime config", async () => {
    vi.mocked(getRuntimeConfig).mockResolvedValue({
      basePath: "/mlflow",
      uiPath: "",
      provider: "",
      gen_ai_gateway_enabled: false,
      authenticated: true,
      workspaces_enabled: false,
    });
    await createUser({
      username: "test",
      display_name: "Test",
      is_admin: false,
      is_service_account: false,
    });
    expect(http).toHaveBeenCalledWith(
      "/mlflow/api/2.0/mlflow/users",
      expect.anything(),
    );
  });

  describe("fetchAllUserDetails", () => {
    it("requests the details endpoint with no query params by default", async () => {
      await fetchAllUserDetails()();
      expect(http).toHaveBeenCalledWith(
        expect.stringContaining("/api/2.0/mlflow/users/details"),
        expect.objectContaining({ method: "GET" }),
      );
    });

    it("appends ?service=false when service is explicitly false", async () => {
      await fetchAllUserDetails(false)();
      expect(http).toHaveBeenCalledWith(
        expect.stringContaining("service=false"),
        expect.anything(),
      );
    });

    it("appends ?service=true when service is explicitly true", async () => {
      await fetchAllUserDetails(true)();
      expect(http).toHaveBeenCalledWith(
        expect.stringContaining("service=true"),
        expect.anything(),
      );
    });
  });

  describe("setUserActive", () => {
    it("sends a PATCH request with active and admin_override", async () => {
      await setUserActive("alice@example.com", false);
      expect(http).toHaveBeenCalledWith(
        expect.stringContaining(
          "/api/2.0/mlflow/users/alice%40example.com/active",
        ),
        expect.objectContaining({
          method: "PATCH",
          body: JSON.stringify({ active: false, admin_override: false }),
        }),
      );
    });

    it("defaults admin_override to false when omitted", async () => {
      await setUserActive("alice@example.com", true);
      expect(http).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          body: JSON.stringify({ active: true, admin_override: false }),
        }),
      );
    });

    it("passes admin_override through when explicitly true", async () => {
      await setUserActive("alice@example.com", false, true);
      expect(http).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          body: JSON.stringify({ active: false, admin_override: true }),
        }),
      );
    });
  });
});
