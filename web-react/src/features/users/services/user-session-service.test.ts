import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  listUserSessions,
  revokeAllUserSessions,
  revokeUserSession,
} from "./user-session-service";
import * as apiUtils from "../../../core/services/api-utils";
import { DYNAMIC_API_ENDPOINTS } from "../../../core/configs/api-endpoints";

vi.mock("../../../core/services/api-utils", () => ({
  request: vi.fn(),
}));

describe("user-session-service", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("listUserSessions GETs and unwraps the sessions", async () => {
    const sessions = [
      {
        pk: 1,
        session_id_prefix: "abcd1234",
        provider_id: "default",
        created_at: null,
        last_seen_at: null,
        expires_at: null,
      },
    ];
    vi.mocked(apiUtils.request).mockResolvedValue({ sessions });
    await expect(listUserSessions("bob@example.com")).resolves.toEqual(sessions);
    expect(apiUtils.request).toHaveBeenCalledWith(
      DYNAMIC_API_ENDPOINTS.USER_SESSIONS("bob@example.com"),
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("revokeUserSession DELETEs one session by pk", async () => {
    await revokeUserSession("bob@example.com", 7);
    expect(apiUtils.request).toHaveBeenCalledWith(
      DYNAMIC_API_ENDPOINTS.USER_SESSION("bob@example.com", 7),
      { method: "DELETE" },
    );
  });

  it("revokeAllUserSessions DELETEs the collection", async () => {
    await revokeAllUserSessions("bob@example.com");
    expect(apiUtils.request).toHaveBeenCalledWith(
      DYNAMIC_API_ENDPOINTS.USER_SESSIONS("bob@example.com"),
      { method: "DELETE" },
    );
  });
});
