import {
  getRuntimeConfig,
  type RuntimeConfig,
} from "../../../shared/services/runtime-config";

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
