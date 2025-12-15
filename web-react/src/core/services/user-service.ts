import { createStaticApiFetcher } from "./create-api-fetcher";
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
