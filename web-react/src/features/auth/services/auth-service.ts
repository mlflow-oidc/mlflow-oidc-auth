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
  CURRENT_USER: (basePath: string) =>
    `${basePath}/api/2.0/mlflow/permissions/users/current`,
} as const;

export async function fetchRuntimeConfig(
  signal?: AbortSignal
): Promise<RuntimeConfig> {
  const maybeGlobal = (
    globalThis as unknown as {
      __RUNTIME_CONFIG__?: RuntimeConfig;
    }
  ).__RUNTIME_CONFIG__;

  if (maybeGlobal) {
    return maybeGlobal;
  }

  const maybeGlobalPromise = (
    globalThis as unknown as {
      __RUNTIME_CONFIG_PROMISE__?: Promise<RuntimeConfig>;
    }
  ).__RUNTIME_CONFIG_PROMISE__;

  if (maybeGlobalPromise) {
    runtimeConfigPromise = maybeGlobalPromise
      .then((cfg) => {
        (
          globalThis as unknown as { __RUNTIME_CONFIG__?: RuntimeConfig }
        ).__RUNTIME_CONFIG__ = cfg;
        runtimeConfigPromise = null;
        return cfg;
      })
      .catch((err) => {
        runtimeConfigPromise = null;
        throw err;
      });

    return runtimeConfigPromise;
  }

  if (runtimeConfigPromise) return runtimeConfigPromise;

  runtimeConfigPromise = http<RuntimeConfig>(AUTH_ENDPOINTS.RUNTIME_CONFIG, {
    method: "GET",
    headers: { "Cache-Control": "no-store" },
    signal,
  })
    .then((cfg) => {
      (
        globalThis as unknown as { __RUNTIME_CONFIG__?: RuntimeConfig }
      ).__RUNTIME_CONFIG__ = cfg;
      runtimeConfigPromise = null;
      return cfg;
    })
    .catch((err) => {
      runtimeConfigPromise = null;
      throw err;
    });

  return runtimeConfigPromise;
}

let runtimeConfigPromise: Promise<RuntimeConfig> | null = null;

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
