import {
  createDynamicApiFetcher,
  createStaticApiFetcher,
} from "./create-api-fetcher";
import { http } from "./http";
import { STATIC_API_ENDPOINTS } from "../configs/api-endpoints";
import type { CurrentUser } from "../../shared/types/user";

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
  return http(STATIC_API_ENDPOINTS.USERS_RESOURCE, {
    method: "POST",
    body: JSON.stringify(data),
  });
};

export const deleteUser = async (username: string) => {
  return http(STATIC_API_ENDPOINTS.USERS_RESOURCE, {
    method: "DELETE",
    body: JSON.stringify({ username }),
  });
};
