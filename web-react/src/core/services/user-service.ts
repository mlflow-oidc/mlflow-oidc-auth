import {
  createDynamicApiFetcher,
  createStaticApiFetcher,
} from "./create-api-fetcher";
import { request } from "./api-utils";
import {
  STATIC_API_ENDPOINTS,
  DYNAMIC_API_ENDPOINTS,
} from "../configs/api-endpoints";
import type { CurrentUser, UserDetails } from "../../shared/types/user";

export const fetchCurrentUser = createStaticApiFetcher<CurrentUser>({
  endpointKey: "GET_CURRENT_USER",
  responseType: {} as CurrentUser,
  headers: {
    "Cache-Control": "no-store",
  },
});

export const fetchAllUsers = createStaticApiFetcher<string[]>({
  endpointKey: "USERS_RESOURCE",
  responseType: [] as string[],
});

export const fetchAllServiceAccounts = createStaticApiFetcher<string[]>({
  endpointKey: "USERS_RESOURCE",
  responseType: [] as string[],
  queryParams: {
    service: true,
  },
});

export const fetchUserDetails = createDynamicApiFetcher<
  CurrentUser,
  "GET_USER_DETAILS"
>({
  endpointKey: "GET_USER_DETAILS",
  responseType: {} as CurrentUser,
});

export const createUser = async (data: {
  username: string;
  display_name: string;
  is_admin: boolean;
  is_service_account: boolean;
}) => {
  return request(STATIC_API_ENDPOINTS.USERS_RESOURCE, {
    method: "POST",
    body: JSON.stringify(data),
  });
};

export const deleteUser = async (username: string) => {
  return request(STATIC_API_ENDPOINTS.USERS_RESOURCE, {
    method: "DELETE",
    body: JSON.stringify({ username }),
  });
};

/**
 * List users with their lifecycle state (admin-only).
 *
 * Returns a fetcher compatible with `useApi`. `service` mirrors the
 * `?service=` query param: omitted returns both users and service accounts,
 * `false` returns users only, `true` returns service accounts only.
 */
export function fetchAllUserDetails(service?: boolean) {
  return (signal?: AbortSignal): Promise<UserDetails[]> =>
    request<UserDetails[]>(STATIC_API_ENDPOINTS.USERS_DETAILS, {
      method: "GET",
      queryParams: service === undefined ? {} : { service },
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
): Promise<UserDetails> => {
  return request<UserDetails>(DYNAMIC_API_ENDPOINTS.USER_ACTIVE(username), {
    method: "PATCH",
    body: JSON.stringify({ active, admin_override: adminOverride }),
  });
};
