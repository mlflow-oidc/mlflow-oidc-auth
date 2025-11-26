import { http } from "./http";
import { getRuntimeConfig } from "../../shared/services/runtime-config";
import type { CurrentUser } from "../../shared/types/user";

export const AUTH_ENDPOINTS = {
  CURRENT_USER: (basePath: string) =>
    `${basePath}/api/2.0/mlflow/permissions/users/current`,
} as const;

export async function fetchCurrentUser(
  signal?: AbortSignal
): Promise<CurrentUser> {
  const cfg = await getRuntimeConfig(signal);
  const currentUserUrl = AUTH_ENDPOINTS.CURRENT_USER(cfg.basePath);

  return http<CurrentUser>(currentUserUrl, {
    method: "GET",
    headers: { "Cache-Control": "no-store" },
    signal,
  });
}
