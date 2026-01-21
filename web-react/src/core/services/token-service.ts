import { createStaticApiFetcher } from "./create-api-fetcher";
import { http } from "./http";
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
  return http<UserTokenCreatedResponse>(STATIC_API_ENDPOINTS.USER_TOKENS, {
    method: "POST",
    body: JSON.stringify(data),
  });
};

export const deleteUserToken = async (tokenId: number): Promise<void> => {
  await http(DYNAMIC_API_ENDPOINTS.DELETE_USER_TOKEN(String(tokenId)), {
    method: "DELETE",
  });
};
