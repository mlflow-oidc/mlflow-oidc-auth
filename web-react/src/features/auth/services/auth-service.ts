import { http } from "../../../core/services/http";
import {
  getRuntimeConfig,
  type RuntimeConfig,
} from "../../../shared/services/runtime-config";

export type AuthStatus = Pick<RuntimeConfig, "authenticated">;

export type Group = {
  group_name: string;
  id: number;
};

export type CurrentUser = {
  display_name: string;
  groups: Group[];
  id: number;
  is_admin: boolean;
  is_service_account: boolean;
  password_expiration: string | null;
  username: string;
};

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
