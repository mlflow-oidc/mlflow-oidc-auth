import { describe, it, expect, vi } from "vitest";
import { createUser, deleteUser } from "./user-service";
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
      authenticated: true,
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
});
