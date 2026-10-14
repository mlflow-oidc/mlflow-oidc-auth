import { createPagedFetcher } from "./paged-list";
import {
  apiRequest,
  type ApiRequestBody,
  type ApiResponse,
} from "./typed-http";
import type { CurrentUser, UserDetails } from "../../shared/types/user";

const USERS = "/api/2.0/mlflow/users";

export const fetchCurrentUser = (signal?: AbortSignal): Promise<CurrentUser> =>
  apiRequest("get", "/api/2.0/mlflow/users/current", {
    signal,
    headers: { "Cache-Control": "no-store" },
  });

export const fetchAllUsers = (signal?: AbortSignal): Promise<string[]> =>
  apiRequest("get", USERS, { signal });

export const fetchAllServiceAccounts = (
  signal?: AbortSignal,
): Promise<string[]> =>
  apiRequest("get", USERS, { query: { service: true }, signal });

/** Paginated usernames for the Users list page. */
export const fetchUsersPage = createPagedFetcher<
  ApiResponse<typeof USERS, "get">,
  string
>(USERS, { extract: (body) => body ?? [], displayKey: (username) => username });

/** Paginated service-account names for the Service Accounts list page. */
export const fetchServiceAccountsPage = createPagedFetcher<
  ApiResponse<typeof USERS, "get">,
  string
>(USERS, {
  extract: (body) => body ?? [],
  displayKey: (username) => username,
  queryParams: { service: true },
});

/**
 * Create a user or service account (admin-only). For a service account,
 * `service_account_source` is "internal" (default) or the id of the provider it
 * signs in through, and `subject` binds an external one to a provider subject now.
 */
export const createUser = async (data: ApiRequestBody<typeof USERS, "post">) =>
  apiRequest("post", USERS, { body: data });

export const deleteUser = async (username: string) =>
  apiRequest("delete", USERS, { body: { username } });

/**
 * List users with their lifecycle state (admin-only).
 *
 * Returns a fetcher compatible with `useApi`. `service` mirrors the
 * `?service=` query param: omitted returns both users and service accounts,
 * `false` returns users only, `true` returns service accounts only.
 */
export function fetchAllUserDetails(service?: boolean) {
  return (signal?: AbortSignal): Promise<UserDetails[]> =>
    apiRequest("get", "/api/2.0/mlflow/users/details", {
      query: service === undefined ? {} : { service },
      signal,
    });
}

/**
 * Activate or deactivate a user (admin-only).
 *
 * @param adminOverride - Break-glass write to a directory-owned account
 * (`managed_by` is `"scim"` or `"oidc:<provider_id>"`). Always audited
 * server-side.
 */
export const setUserActive = async (
  username: string,
  active: boolean,
  adminOverride: boolean = false,
): Promise<UserDetails> =>
  apiRequest("patch", "/api/2.0/mlflow/users/{username}/active", {
    path: { username },
    body: { active, admin_override: adminOverride },
  });
