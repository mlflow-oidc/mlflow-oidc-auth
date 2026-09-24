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

/** How a recorded SCIM request ended. `auth_failed` rows carry no token. */
export type ScimActivityOutcome =
  | "ok"
  | "client_error"
  | "server_error"
  | "auth_failed";

/** One `/scim/v2` request from the activity log (`GET /api/2.0/mlflow/scim/activity`). */
export type ScimActivityEntry = {
  id: number;
  at: string;
  token_id: number | null;
  token_name: string | null;
  method: string;
  /** Route template, e.g. `/Users/{user_id}` — never the concrete path. */
  path: string;
  /** The SCIM `id` the request addressed, when it addressed one. */
  resource_id: string | null;
  status: number;
  outcome: ScimActivityOutcome;
  /** Short SCIM error (`scimType: detail`), never a request body. */
  error: string | null;
  duration_ms: number | null;
};

export type ScimActivityPage = {
  activity: ScimActivityEntry[];
  /** Cursor for the next page (`before=`), or null when this page was the last. */
  next_before: number | null;
};

export type ScimActivityQuery = {
  limit?: number;
  before?: number;
  outcome?: ScimActivityOutcome;
  token_id?: number;
};

export type ScimTokenStatus = {
  token_id: number;
  name: string;
  active: boolean;
  last_used_at: string | null;
  last_success_at: string | null;
  last_error_at: string | null;
  last_error: string | null;
  last_error_status: number | null;
  requests_24h: number;
  errors_24h: number;
};

/** `GET /api/2.0/mlflow/scim/status`. */
export type ScimProvisioningStatus = {
  /** true: a success within the healthy window; false: none; null: SCIM never used. */
  provisioning_healthy: boolean | null;
  last_success_at: string | null;
  last_error_at: string | null;
  last_error: string | null;
  requests_24h: number;
  errors_24h: number;
  auth_failures_24h: number;
  last_auth_failure_at: string | null;
  healthy_window_seconds: number;
  retention_days: number;
  tokens: ScimTokenStatus[];
};
