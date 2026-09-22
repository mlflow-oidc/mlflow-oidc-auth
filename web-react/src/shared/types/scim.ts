export type ScimToken = {
  id: number;
  name: string;
  token_prefix: string;
  created_at: string;
  created_by: string;
  last_used_at: string | null;
  expires_at: string | null;
  revoked_at: string | null;
};

export type ScimTokenWithSecret = ScimToken & {
  /** Plaintext bearer token. Only ever present on the create/rotate response, shown once. */
  token: string;
  /** Present on a rotate response: the id of the token this one replaces. */
  replaces?: number;
};

export type CreateScimTokenRequest = {
  name: string;
  expires_at?: string;
};
