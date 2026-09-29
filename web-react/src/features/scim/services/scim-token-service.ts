import { request } from "../../../core/services/api-utils";
import {
  STATIC_API_ENDPOINTS,
  DYNAMIC_API_ENDPOINTS,
} from "../../../core/configs/api-endpoints";
import { createPagedFetcher } from "../../../core/services/paged-list";
import type {
  ScimToken,
  ScimTokenWithSecret,
  CreateScimTokenRequest,
} from "../../../shared/types/scim";

/** Paginated SCIM tokens; searched on the token name. */
export const fetchScimTokensPage = createPagedFetcher<
  ScimToken[] | undefined,
  ScimToken
>(STATIC_API_ENDPOINTS.SCIM_TOKENS_RESOURCE, {
  extract: (body) => body ?? [],
  displayKey: (token) => token.name,
});

export const createScimToken = async (
  data: CreateScimTokenRequest,
): Promise<ScimTokenWithSecret> => {
  return request<ScimTokenWithSecret>(
    STATIC_API_ENDPOINTS.SCIM_TOKENS_RESOURCE,
    {
      method: "POST",
      body: JSON.stringify(data),
    },
  );
};

export const rotateScimToken = async (
  tokenId: number,
): Promise<ScimTokenWithSecret> => {
  return request<ScimTokenWithSecret>(
    DYNAMIC_API_ENDPOINTS.SCIM_TOKEN_ROTATE(tokenId),
    {
      method: "POST",
    },
  );
};

export const revokeScimToken = async (tokenId: number): Promise<ScimToken> => {
  return request<ScimToken>(DYNAMIC_API_ENDPOINTS.SCIM_TOKEN_DETAIL(tokenId), {
    method: "DELETE",
  });
};
