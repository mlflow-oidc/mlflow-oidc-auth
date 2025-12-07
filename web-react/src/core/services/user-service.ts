import { createApiFetcher } from "./api-utils";
import type { CurrentUser } from "../../shared/types/user";

export const fetchCurrentUser = createApiFetcher<CurrentUser>({
  endpointKey: "GET_CURRENT_USER",
  responseType: {} as CurrentUser,
  headers: {
    "Cache-Control": "no-store",
  },
});

export const fetchAllUsers = createApiFetcher<string[]>({
  endpointKey: "ALL_USERS",
  responseType: [] as string[],
});

export const fetchAllServiceAccounts = createApiFetcher<string[]>({
  endpointKey: "ALL_USERS",
  responseType: [] as string[],
  queryParams: {
    service: true,
  },
});
