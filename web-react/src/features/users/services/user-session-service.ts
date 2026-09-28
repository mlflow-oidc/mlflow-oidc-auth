import { request } from "../../../core/services/api-utils";
import { DYNAMIC_API_ENDPOINTS } from "../../../core/configs/api-endpoints";
import type { UserSession } from "../../../shared/types/user";

export type RevokeSessionsResult = { revoked: number };

export const listUserSessions = async (
  username: string,
  signal?: AbortSignal,
): Promise<UserSession[]> => {
  const body = await request<{ sessions: UserSession[] }>(
    DYNAMIC_API_ENDPOINTS.USER_SESSIONS(username),
    { method: "GET", signal },
  );
  return body.sessions;
};

export const revokeUserSession = async (
  username: string,
  sessionPk: number,
): Promise<RevokeSessionsResult> => {
  return request<RevokeSessionsResult>(
    DYNAMIC_API_ENDPOINTS.USER_SESSION(username, sessionPk),
    { method: "DELETE" },
  );
};

export const revokeAllUserSessions = async (
  username: string,
): Promise<RevokeSessionsResult> => {
  return request<RevokeSessionsResult>(
    DYNAMIC_API_ENDPOINTS.USER_SESSIONS(username),
    { method: "DELETE" },
  );
};
