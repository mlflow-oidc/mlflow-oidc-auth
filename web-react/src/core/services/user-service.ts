import { createStaticApiFetcher } from "./create-api-fetcher";
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
  endpointKey: "ALL_USERS",
  responseType: [] as string[],
});

export const fetchAllServiceAccounts = createStaticApiFetcher<string[]>({
  endpointKey: "ALL_USERS",
  responseType: [] as string[],
  queryParams: {
    service: true,
  },
});

export const createServiceAccount = async (data: {
  username: string;
  display_name: string;
  is_admin: boolean;
  is_service_account: boolean;
}) => {
  return http(STATIC_API_ENDPOINTS.CREATE_USER, {
    method: "POST",
    body: JSON.stringify(data),
  });
};
