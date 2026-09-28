export type Group = {
  id: number;
  group_name: string;
};

export type CurrentUser = {
  display_name: string;
  groups: Group[];
  id: number;
  is_admin: boolean;
  is_service_account: boolean;
  username: string;
};

/**
 * managed_by values: "manual", "scim", or "oidc:<provider_id>".
 */
export type ManagedBy = string;

export type UserDetails = {
  username: string;
  display_name: string;
  is_admin: boolean;
  is_service_account: boolean;
  active: boolean;
  managed_by: ManagedBy;
};

/**
 * A live server-side session as the admin API lists it. Never the full session id: that is a
 * bearer credential. `pk` addresses the session for revocation.
 */
export type UserSession = {
  pk: number;
  session_id_prefix: string;
  provider_id: string | null;
  created_at: string | null;
  last_seen_at: string | null;
  expires_at: string | null;
};

/**
 * One of a user's named API access tokens. Never carries the secret: only the create response
 * does, once (see {@link UserTokenWithSecret}).
 */
export type UserToken = {
  id: number;
  name: string;
  /**
   * Non-secret lookup prefix, embedded in the token as `mlf_<prefix>_<secret>`. Null for a secret
   * carried over from before named tokens.
   */
  token_prefix: string | null;
  created_at: string;
  created_by: string | null;
  expires_at: string;
  last_used_at: string | null;
  /** False once the token has expired. */
  active: boolean;
};

export type UserTokenWithSecret = UserToken & {
  /** Plaintext token. Only present on the create response, shown once. */
  token: string;
};

export type CreateUserTokenRequest = {
  name: string;
  /** ISO 8601 timestamp; the backend caps it at one year from now. */
  expiration: string;
};

export interface UserContextType {
  currentUser: CurrentUser | null;
  setCurrentUser: (user: CurrentUser | null) => void;
  isLoading: boolean;
  setIsLoading: (loading: boolean) => void;
  error: Error | null;
  setError: (error: Error | null) => void;
}
