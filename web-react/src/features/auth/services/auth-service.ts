import { http } from "../../../core/services/http";

export type RuntimeConfig = {
  basePath: string;
  uiPath: string;
  provider: string;
  authenticated: boolean;
};

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
  RUNTIME_CONFIG: "config.json",
  CURRENT_USER: "/api/2.0/mlflow/permissions/users/current",
} as const;

export async function fetchRuntimeConfig(
  signal?: AbortSignal
): Promise<RuntimeConfig> {
  return http<RuntimeConfig>(AUTH_ENDPOINTS.RUNTIME_CONFIG, {
    method: "GET",
    headers: { "Cache-Control": "no-store" },
    signal,
  });
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
  return http<CurrentUser>(AUTH_ENDPOINTS.CURRENT_USER, {
    method: "GET",
    headers: { "Cache-Control": "no-store" },
    signal,
  });
}
