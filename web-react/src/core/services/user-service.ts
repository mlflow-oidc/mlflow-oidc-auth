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
