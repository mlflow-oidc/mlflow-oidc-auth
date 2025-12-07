import { http } from "./http";
import { getRuntimeConfig } from "../../shared/services/runtime-config";
import type { CurrentUser } from "../../shared/types/user";
import { API_ENDPOINTS } from "../configs/api-endpoints";

export async function fetchCurrentUser(
  signal?: AbortSignal
): Promise<CurrentUser> {
  const cfg = await getRuntimeConfig(signal);
  const currentUserUrl = `${cfg.basePath}${API_ENDPOINTS.GET_CURRENT_USER}`;

  return http<CurrentUser>(currentUserUrl, {
    method: "GET",
    headers: { "Cache-Control": "no-store" },
    signal,
  });
}

export async function fetchAllUsers(signal?: AbortSignal): Promise<string[]> {
  const cfg = await getRuntimeConfig(signal);
  const allUsersUrl = `${cfg.basePath}${API_ENDPOINTS.ALL_USERS}`;

  return http<string[]>(allUsersUrl, {
    method: "GET",
    signal,
  });
}

export async function fetchAllServiceAccounts(
  signal?: AbortSignal
): Promise<string[]> {
  const cfg = await getRuntimeConfig(signal);
  const allServiceAccountsUrl = `${cfg.basePath}${API_ENDPOINTS.ALL_USERS}?service=true`;

  return http<string[]>(allServiceAccountsUrl, {
    method: "GET",
    signal,
  });
}
