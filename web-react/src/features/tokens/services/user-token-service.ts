import { request } from "../../../core/services/api-utils";
import {
  DYNAMIC_API_ENDPOINTS,
  STATIC_API_ENDPOINTS,
} from "../../../core/configs/api-endpoints";
import type {
  CreateUserTokenRequest,
  UserToken,
  UserTokenWithSecret,
} from "../../../shared/types/user";

/**
 * Whose tokens a call addresses. `undefined` is the signed-in user (the `/users/tokens`
 * endpoints); a username is another account, through the admin-only `/users/{username}/tokens`
 * endpoints.
 */
export type TokenOwner = string | undefined;

const collectionEndpoint = (owner: TokenOwner): string =>
  owner === undefined
    ? STATIC_API_ENDPOINTS.CURRENT_USER_TOKENS
    : DYNAMIC_API_ENDPOINTS.USER_TOKENS(owner);

const itemEndpoint = (owner: TokenOwner, tokenId: number): string =>
  owner === undefined
    ? DYNAMIC_API_ENDPOINTS.CURRENT_USER_TOKEN(tokenId)
    : DYNAMIC_API_ENDPOINTS.USER_TOKEN(owner, tokenId);

/**
 * List an account's API tokens, expired ones included.
 *
 * @param owner - The account, or `undefined` for the signed-in user.
 * @param signal - Optional abort signal.
 * @returns The tokens. Never contains a secret.
 */
export async function listUserTokens(
  owner: TokenOwner,
  signal?: AbortSignal,
): Promise<UserToken[]> {
  const response = await request<{ tokens?: UserToken[] }>(
    collectionEndpoint(owner),
    { signal },
  );
  return response.tokens ?? [];
}

/**
 * Issue a new named token.
 *
 * @param owner - The account, or `undefined` for the signed-in user.
 * @param data - Name and ISO 8601 expiration.
 * @returns The token record plus its plaintext, which the server never returns again.
 */
export async function createUserToken(
  owner: TokenOwner,
  data: CreateUserTokenRequest,
): Promise<UserTokenWithSecret> {
  return request<UserTokenWithSecret>(collectionEndpoint(owner), {
    method: "POST",
    body: JSON.stringify(data),
  });
}

/**
 * Delete one token; it stops authenticating immediately.
 *
 * @param owner - The account, or `undefined` for the signed-in user.
 * @param tokenId - The token's id.
 */
export async function deleteUserToken(
  owner: TokenOwner,
  tokenId: number,
): Promise<{ deleted: number }> {
  return request<{ deleted: number }>(itemEndpoint(owner, tokenId), {
    method: "DELETE",
  });
}

/**
 * Admin only: revoke every token of an account.
 *
 * @param username - The account.
 * @returns How many tokens were revoked.
 */
export async function revokeAllUserTokens(
  username: string,
): Promise<{ revoked: number }> {
  return request<{ revoked: number }>(
    DYNAMIC_API_ENDPOINTS.USER_TOKENS(username),
    { method: "DELETE" },
  );
}
