import { http } from "../../../core/services/http";
import {
  getRuntimeConfig,
  type RuntimeConfig,
} from "../../../shared/services/runtime-config";
import type { CurrentUser } from "../../../shared/types/user";

export type AuthStatus = Pick<RuntimeConfig, "authenticated">;

export const AUTH_ENDPOINTS = {
  CURRENT_USER: (basePath: string) =>
    `${basePath}/api/2.0/mlflow/permissions/users/current`,
} as const;

export async function fetchRuntimeConfig(
  signal?: AbortSignal
): Promise<RuntimeConfig> {
  return getRuntimeConfig(signal);
}

export async function fetchAuthStatus(
  signal?: AbortSignal
): Promise<AuthStatus> {
  const cfg = await fetchRuntimeConfig(signal);
  return { authenticated: !!cfg.authenticated };
}

export async function fetchCurrentUser(
  signal?: AbortSignal
): Promise<CurrentUser> {
  const cfg = await fetchRuntimeConfig(signal);
  const currentUserUrl = AUTH_ENDPOINTS.CURRENT_USER(cfg.basePath);
  return http<CurrentUser>(currentUserUrl, {
    method: "GET",
    headers: { "Cache-Control": "no-store" },
    signal,
  });
}
