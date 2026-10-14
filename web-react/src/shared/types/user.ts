import type { components } from "../../core/types/generated/openapi";

type Schemas = components["schemas"];

/** `GET /users/current` and `GET /users/{username}`. Generated from the API contract. */
export type CurrentUser = Schemas["CurrentUserProfile"];

/**
 * A user with its lifecycle state (`GET /users/details`). Generated from the API contract.
 * `managed_by` is "manual", "scim", "oidc:<provider_id>" or "saml:<provider_id>";
 * `service_account_source` is "internal" or a provider id for a service account, null for a person.
 */
export type UserDetails = Schemas["UserDetail"];

/**
 * A live server-side session as the admin API lists it. Never the full session id: that is a
 * bearer credential. `pk` addresses the session for revocation. Generated from the API contract.
 */
export type UserSession = Schemas["UserSessionRecord"];

/**
 * One of a user's named API access tokens. Never carries the secret: only the create response
 * does, once (see {@link UserTokenWithSecret}). `token_prefix` is null for a secret carried over
 * from before named tokens; `active` is false once the token has expired. Generated from the API
 * contract.
 */
export type UserToken = Schemas["UserTokenRecord"];

/** A newly issued token: the plaintext `token` is in this response only, shown once. */
export type UserTokenWithSecret = Schemas["UserTokenCreatedResponse"];

/** `expiration` is ISO 8601; the backend caps it at one year from now. */
export type CreateUserTokenRequest = Schemas["CreateUserTokenRequest"];

export interface UserContextType {
  currentUser: CurrentUser | null;
  setCurrentUser: (user: CurrentUser | null) => void;
  isLoading: boolean;
  setIsLoading: (loading: boolean) => void;
  error: Error | null;
  setError: (error: Error | null) => void;
}
