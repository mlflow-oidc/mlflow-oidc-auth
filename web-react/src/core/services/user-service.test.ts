import { describe, it, expect, vi } from "vitest";
import { createUser, deleteUser } from "./user-service";
import { http } from "./http";

vi.mock("./http");

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
});
