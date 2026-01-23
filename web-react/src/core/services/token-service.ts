import { createStaticApiFetcher } from "./create-api-fetcher";
import { http } from "./http";
import { resolveUrl } from "./api-utils";
import {
  STATIC_API_ENDPOINTS,
  DYNAMIC_API_ENDPOINTS,
} from "../configs/api-endpoints";

export interface UserToken {
  id: number;
  name: string;
  created_at: string;
  expires_at: string | null;
  last_used_at: string | null;
  [key: string]: unknown;
}

export interface UserTokenListResponse {
  tokens: UserToken[];
}

export interface UserTokenCreatedResponse {
  id: number;
  name: string;
  token: string;
  created_at: string;
  expires_at: string | null;
  message: string;
}

export interface CreateTokenRequest {
  name: string;
  expiration?: string;
}

export const fetchUserTokens = createStaticApiFetcher<UserTokenListResponse>({
  endpointKey: "USER_TOKENS",
  responseType: {} as UserTokenListResponse,
});

export const createUserToken = async (
  data: CreateTokenRequest
): Promise<UserTokenCreatedResponse> => {
  const url = await resolveUrl(STATIC_API_ENDPOINTS.USER_TOKENS, {});
  return http<UserTokenCreatedResponse>(url, {
    method: "POST",
    body: JSON.stringify(data),
  });
};

export const deleteUserToken = async (tokenId: number): Promise<void> => {
  const url = await resolveUrl(DYNAMIC_API_ENDPOINTS.DELETE_USER_TOKEN(String(tokenId)), {});
  await http(url, {
    method: "DELETE",
  });
};
