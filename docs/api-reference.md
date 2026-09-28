# API Reference

The plugin exposes ~205 REST API endpoints for authentication, permission management, workspace management, webhooks, and trash operations. This reference covers the plugin's own endpoints — MLflow's native tracking/registry API is not documented here (see [MLflow docs](https://mlflow.org/docs/latest/rest-api.html)).

## Authentication

All endpoints except health probes, login/callback, and static files require authentication. The plugin supports three authentication methods (tried in order):

1. **Basic Auth**: `Authorization: Basic base64(username:password)` — the password is one of the user's named access tokens (see [Access tokens](#access-tokens))
2. **JWT Bearer Token**: `Authorization: Bearer <jwt_token>`
3. **Session Cookie**: Set automatically after OIDC login

When workspaces are enabled, include the `X-MLFLOW-WORKSPACE` header to specify the active workspace.

## Permission Levels

Request/response bodies reference these permission values:

| Value | Description |
|-------|-------------|
| `READ` | Read-only access |
| `USE` | Read + use (e.g., invoke endpoints) |
| `EDIT` | Read + use + update |
| `MANAGE` | Full control including delete and permission management |
| `NO_PERMISSIONS` | Explicit denial |

---

## Auth Endpoints

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/login` | Public | Initiate OIDC login flow (redirects to OIDC provider) |
| GET | `/callback` | Public | Handle OIDC callback (exchange code for tokens, establish session) |
| GET | `/logout` | Public | Clear session and redirect to OIDC provider logout |
| GET | `/auth/status` | Public | Return current authentication status |

**`GET /auth/status` response:**
```json
{
  "authenticated": true,
  "username": "alice@example.com",
  "provider": "oidc"
}
```

---

## Health Endpoints

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/health` | Public | Basic health check |
| GET | `/health/live` | Public | Liveness probe |
| GET | `/health/ready` | Public | Readiness probe (checks OIDC + database) |
| GET | `/health/startup` | Public | Startup probe (checks OIDC initialization) |

**`GET /health/ready` response (200):**
```json
{
  "status": "ready",
  "checks": {
    "oidc": "ok",
    "database": "ok"
  }
}
```

---

## User Management

Base path: `/api/2.0/mlflow/users`

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/api/2.0/mlflow/users` | Authenticated | List users. Query param `service=true` to include service accounts |
| POST | `/api/2.0/mlflow/users` | Admin | Create a new user |
| DELETE | `/api/2.0/mlflow/users` | Admin | Delete a user |
| GET | `/api/2.0/mlflow/users/current` | Authenticated | Get current user's profile |
| GET | `/api/2.0/mlflow/users/{username}` | Admin | Get a specific user's profile |
| GET | `/api/2.0/mlflow/users/tokens` | Authenticated | List the caller's access tokens |
| POST | `/api/2.0/mlflow/users/tokens` | Session or IdP bearer token | Create a named access token for the caller |
| DELETE | `/api/2.0/mlflow/users/tokens/{token_id}` | Authenticated | Delete one of the caller's access tokens |
| GET | `/api/2.0/mlflow/users/{username}/tokens` | Admin | List a user's or service account's access tokens |
| POST | `/api/2.0/mlflow/users/{username}/tokens` | Admin, session or IdP bearer token | Create a named access token for a user or service account |
| DELETE | `/api/2.0/mlflow/users/{username}/tokens/{token_id}` | Admin | Delete one of a user's access tokens |
| DELETE | `/api/2.0/mlflow/users/{username}/tokens` | Admin | Revoke every access token of a user |
| PATCH | `/api/2.0/mlflow/users/access-token` | Session or IdP bearer token | Issue a new `default` access token, replacing the previous one |

**`POST /api/2.0/mlflow/users` request:**
```json
{
  "username": "alice@example.com",
  "display_name": "Alice",
  "is_admin": false
}
```

**`GET /api/2.0/mlflow/users/current` response:**
```json
{
  "username": "alice@example.com",
  "display_name": "Alice",
  "is_admin": false,
  "groups": ["mlflow-users", "data-team"],
  "experiment_permissions": [...],
  "registered_model_permissions": [...]
}
```

`password_expiration` is no longer part of this response, or of `GET /{username}` — see
[Access tokens](#access-tokens).

### Access tokens

Each user (and service account) can hold up to 20 unexpired named access tokens. A token is used
as the password of HTTP basic auth (`username:token`) — for example `MLFLOW_TRACKING_USERNAME` /
`MLFLOW_TRACKING_PASSWORD`. A token looks like `mlf_3f9a0c1b_<secret>`: the `mlf_<prefix>_` part is
not secret and is shown in listings to tell tokens apart; only a hash of the whole value is stored,
and the plaintext is returned exactly once, at creation. Every token must expire, at most one year
(366 days) from creation, and names are unique per user (255 characters max, case-sensitive as
stored).

Issuing a token — any endpoint that returns a new one, including `PATCH /access-token` — requires
a signed-in session or a user's bearer token from an interactive IdP. A request authenticated with
an access token, or with a bearer token from a non-interactive provider (a Kubernetes service
account, a provider configured `interactive: false`), gets `403`: a leaked or short-lived
credential cannot mint a year-long replacement. Listing and deleting tokens works with
any credential.

**`GET /api/2.0/mlflow/users/tokens` response** (own tokens; `/{username}/tokens` for an admin
listing another user's, same shape). Expired tokens are included; neither ever contains a secret:
```json
{
  "tokens": [
    {
      "id": 7,
      "name": "laptop",
      "token_prefix": "3f9a0c1b",
      "created_at": "2026-09-28T10:00:00+00:00",
      "created_by": "alice@example.com",
      "expires_at": "2027-01-01T00:00:00+00:00",
      "last_used_at": null,
      "active": true
    }
  ]
}
```

**`POST /api/2.0/mlflow/users/tokens` request** (`/{username}/tokens` for an admin issuing one for
another user or a service account):
```json
{
  "name": "laptop",
  "expiration": "2027-01-01T00:00:00Z"
}
```

**response (`201`)** — the same object as above, plus the plaintext:
```json
{
  "id": 7,
  "name": "laptop",
  "token_prefix": "3f9a0c1b",
  "created_at": "2026-09-28T10:00:00+00:00",
  "created_by": "alice@example.com",
  "expires_at": "2027-01-01T00:00:00+00:00",
  "last_used_at": null,
  "active": true,
  "token": "mlf_3f9a0c1b_<secret>"
}
```

`400` for a bad name or expiration, `403` when not an interactive sign-in (see above) or, on
`/{username}/tokens`, not an admin, `404` for an unknown user, `409` for a duplicate name, at the
20-token cap, or for a deactivated user, `422` for a missing field. Issuing a token also deletes the
user's expired tokens, which frees their names.

`DELETE /api/2.0/mlflow/users/tokens/{token_id}` (own) or `/{username}/tokens/{token_id}` (admin)
returns `{"deleted": 1}`; `404` if it is not that user's token — another user's token id reads
exactly like one that does not exist. `DELETE /api/2.0/mlflow/users/{username}/tokens` (admin,
revoke all) returns `{"revoked": <count>}`.

**`PATCH /api/2.0/mlflow/users/access-token` request** (all fields optional):
```json
{"username": "alice@example.com", "expiration": "2027-01-01T00:00:00Z"}
```

Issues a token named `default`, deleting the previous `default` token in the same transaction;
the user's other named tokens are untouched. `username` for another user is admin-only. An
omitted `expiration` now means one year from now (previously: never expires). `400` for a bad
expiration, `403` when not an interactive sign-in or for a non-admin naming another user, `404` for
an unknown user, `409` at the cap or for a deactivated user. Response:
```json
{"token": "mlf_...", "expires_at": "2027-01-01T00:00:00+00:00", "message": "Token for alice@example.com has been created"}
```

Token issuance and deletion are audited; no event ever carries a secret. `detail` per event:

| Event | When | `detail` |
|-------|------|----------|
| `user.token_create` | `POST .../tokens` | `token_id`, `token_prefix`, `name`, `expiration` |
| `user.token_rotate` | `PATCH /access-token` | `token_id`, `token_prefix`, `name`, `expiration`, `expiration_defaulted`, `replaced` |
| `user.token_delete` | `DELETE .../tokens/{token_id}` | `token_id`, `token_prefix`, `name` |
| `user.tokens_revoked` | `DELETE /{username}/tokens` | `tokens` (count), `reason: "admin_revoke_all"` |

**Upgrading.** Migration `f6a7b8c9d0e1` carries each user's existing unexpired secret over as a
token named `default` with no prefix; it keeps working unchanged, and a secret that never expired
is given an expiry one year from the upgrade. Before this release every user was created with a
random secret nobody was shown, and it cannot be told apart from one a person was issued, so
almost every user will see a `default` token labelled "Carried over" in the Tokens tab. It is
harmless — nobody knows it — and can be deleted. Breaking changes:

- `PATCH /access-token` now requires a signed-in session or an interactive IdP bearer token
  (`403` with basic auth or a workload token), so automation can no longer rotate its own token.
- Every token now expires (at most one year); a previously non-expiring secret gets a one-year
  expiry at upgrade.
- `password_expiration` is no longer returned from `GET /users/current` or `GET /users/{username}`.
- Deactivating a user now deletes all of their access tokens, rather than replacing the single
  secret with an undisclosed expired one.

---

## Resource Permission Listing

These endpoints list resources with their permission summaries. Used by the admin UI for the permission management views.

### Experiments

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/api/2.0/mlflow/permissions/experiments` | Authenticated | List experiments with permission summary |
| GET | `/api/2.0/mlflow/permissions/experiments/{id}/users` | Experiment MANAGE | List user permissions for an experiment |
| GET | `/api/2.0/mlflow/permissions/experiments/{id}/groups` | Experiment MANAGE | List group permissions for an experiment |

### Registered Models

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/api/2.0/mlflow/permissions/registered-models` | Authenticated | List models with permission summary |
| GET | `/api/2.0/mlflow/permissions/registered-models/{name}/users` | Model MANAGE | List user permissions for a model |
| GET | `/api/2.0/mlflow/permissions/registered-models/{name}/groups` | Model MANAGE | List group permissions for a model |

### Prompts

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/api/2.0/mlflow/permissions/prompts` | Authenticated | List prompts with permission summary |
| GET | `/api/2.0/mlflow/permissions/prompts/{name}/users` | Prompt MANAGE | List user permissions for a prompt |
| GET | `/api/2.0/mlflow/permissions/prompts/{name}/groups` | Prompt MANAGE | List group permissions for a prompt |

### Scorers

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/api/3.0/mlflow/permissions/scorers/{experiment_id}` | Authenticated | List scorers for an experiment |
| GET | `/api/3.0/mlflow/permissions/scorers/{experiment_id}/{name}/users` | Scorer MANAGE | List user permissions |
| GET | `/api/3.0/mlflow/permissions/scorers/{experiment_id}/{name}/groups` | Scorer MANAGE | List group permissions |

### Gateway Endpoints

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/api/2.0/mlflow/permissions/gateways/endpoints` | Authenticated | List gateway endpoints |
| GET | `/api/2.0/mlflow/permissions/gateways/endpoints/{name}/users` | Endpoint MANAGE | List user permissions |
| GET | `/api/2.0/mlflow/permissions/gateways/endpoints/{name}/groups` | Endpoint MANAGE | List group permissions |

### Gateway Secrets

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/api/2.0/mlflow/permissions/gateways/secrets` | Authenticated | List gateway secrets |
| GET | `/api/2.0/mlflow/permissions/gateways/secrets/{name}/users` | Secret MANAGE | List user permissions |
| GET | `/api/2.0/mlflow/permissions/gateways/secrets/{name}/groups` | Secret MANAGE | List group permissions |

### Gateway Model Definitions

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/api/2.0/mlflow/permissions/gateways/model-definitions` | Authenticated | List model definitions |
| GET | `/api/2.0/mlflow/permissions/gateways/model-definitions/{name}/users` | Model Def MANAGE | List user permissions |
| GET | `/api/2.0/mlflow/permissions/gateways/model-definitions/{name}/groups` | Model Def MANAGE | List group permissions |

---

## User Permission CRUD

Base path: `/api/2.0/mlflow/permissions/users/{username}`

These endpoints manage per-user permissions for each resource type. The pattern is identical for all resource types.

### Direct Permissions

For each resource type, the following CRUD operations are available:

| Method | Path Pattern | Auth | Purpose |
|--------|-------------|------|---------|
| GET | `/{username}/{resource-type}` | Authenticated | List all permissions for this user |
| POST | `/{username}/{resource-type}/{resource-id}` | Resource MANAGE | Grant permission |
| GET | `/{username}/{resource-type}/{resource-id}` | Resource MANAGE | Get specific permission |
| PATCH | `/{username}/{resource-type}/{resource-id}` | Resource MANAGE | Update permission |
| DELETE | `/{username}/{resource-type}/{resource-id}` | Resource MANAGE | Revoke permission |

**Resource types and paths:**

| Resource | Path Segment | Resource ID |
|----------|-------------|-------------|
| Experiments | `experiments` | `{experiment_id}` |
| Registered Models | `registered-models` | `{name}` |
| Prompts | `prompts` | `{name}` |
| Scorers | `scorers` | `{experiment_id}/{scorer_name}` |
| Gateway Endpoints | `gateways/endpoints` | `{name}` |
| Gateway Secrets | `gateways/secrets` | `{name}` |
| Gateway Model Definitions | `gateways/model-definitions` | `{name}` |

**Request body (POST/PATCH):**
```json
{
  "permission": "EDIT"
}
```

### Regex Pattern Permissions

For each resource type, regex pattern permissions are also available:

| Method | Path Pattern | Auth | Purpose |
|--------|-------------|------|---------|
| POST | `/{username}/{resource-type}-patterns` | Admin | Create regex pattern permission |
| GET | `/{username}/{resource-type}-patterns` | Authenticated | List regex pattern permissions |
| GET | `/{username}/{resource-type}-patterns/{id}` | Admin | Get specific pattern permission |
| PATCH | `/{username}/{resource-type}-patterns/{id}` | Admin | Update pattern permission |
| DELETE | `/{username}/{resource-type}-patterns/{id}` | Admin | Delete pattern permission |

**Request body (POST/PATCH):**
```json
{
  "pattern": "^prod-.*",
  "permission": "READ",
  "priority": 1
}
```

**Pattern path segments:** `experiment-patterns`, `registered-models-patterns`, `prompts-patterns`, `scorer-patterns`, `gateways/endpoints-patterns`, `gateways/secrets-patterns`, `gateways/model-definitions-patterns`

**Total: 70 user permission endpoints** (7 resource types x 10 operations each)

---

## Group Permission CRUD

Base path: `/api/2.0/mlflow/permissions/groups`

### Group Listing

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/api/2.0/mlflow/permissions/groups` | Authenticated | List all groups |
| POST | `/api/2.0/mlflow/permissions/groups` | Admin | Create a group |
| GET | `/api/2.0/mlflow/permissions/groups/{group_name}/users` | Admin | List group members |

**`POST /api/2.0/mlflow/permissions/groups` request:**
```json
{
  "group_name": "data-team"
}
```

Groups are otherwise created from the identity provider claims when a member signs in, so a group cannot be granted permissions before its first login. Creating a group up front lifts that ordering constraint for automated provisioning. The call is idempotent: it returns `201` when the group is created and `200` when it already exists — including a group a directory (SCIM) already owns, which keeps that ownership untouched. The name is validated with the same rules as a SCIM `displayName`: stripped, non-empty, at most 255 characters, no control characters, and none of `/ ? # %`.

### Group Direct Permissions

Same CRUD pattern as user permissions, but scoped to groups:

| Method | Path Pattern | Auth | Purpose |
|--------|-------------|------|---------|
| GET | `/{group_name}/{resource-type}` | Authenticated | List group's permissions |
| POST | `/{group_name}/{resource-type}/{resource-id}` | Resource MANAGE or Admin | Grant permission |
| PATCH | `/{group_name}/{resource-type}/{resource-id}` | Resource MANAGE or Admin | Update permission |
| DELETE | `/{group_name}/{resource-type}/{resource-id}` | Resource MANAGE or Admin | Revoke permission |

### Group Regex Pattern Permissions

| Method | Path Pattern | Auth | Purpose |
|--------|-------------|------|---------|
| POST | `/{group_name}/{resource-type}-patterns` | Admin | Create regex pattern permission |
| GET | `/{group_name}/{resource-type}-patterns` | Authenticated | List regex pattern permissions |
| GET | `/{group_name}/{resource-type}-patterns/{id}` | Admin | Get specific pattern permission |
| PATCH | `/{group_name}/{resource-type}-patterns/{id}` | Admin | Update pattern permission |
| DELETE | `/{group_name}/{resource-type}-patterns/{id}` | Admin | Delete pattern permission |

**Total: 70 group permission endpoints** (3 group-level + 7 resource types x ~9.5 operations each)

---

## Trash Management

Base path: `/oidc/trash`

All trash endpoints require **admin** permissions.

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/oidc/trash/experiments` | List deleted experiments |
| GET | `/oidc/trash/runs` | List deleted runs. Query: `experiment_ids`, `older_than` |
| POST | `/oidc/trash/cleanup` | Permanently delete trashed items. Query: `older_than`, `run_ids`, `experiment_ids` |
| POST | `/oidc/trash/experiments/{experiment_id}/restore` | Restore a deleted experiment |
| POST | `/oidc/trash/runs/{run_id}/restore` | Restore a deleted run |

When workspaces are enabled, trash operations are automatically scoped to the active workspace.

`POST /oidc/trash/cleanup` deletes a run's artifacts before hard-deleting its metadata. A run
whose artifact URI uses the proxied `mlflow-artifacts:` scheme (the tracking server serves the
artifacts itself) is resolved against the server's `--artifacts-destination` root, the same way
MLflow's own server resolves proxied artifacts. If artifact deletion fails for a run, that run's
metadata is **not** deleted — it stays in the trash and is reported in the response's
`failed_runs` list with a short, fixed reason (the underlying exception is written to the
server log, not returned), so a run is never hard-deleted while its artifacts are still
known to exist. Before hard-deleting an experiment, the endpoint always checks whether it still
owns any run — for any reason a run above was kept (a failed artifact deletion, an age or
lifecycle-stage check, or a lookup failure), not only an artifact-deletion failure. If one does,
the experiment is kept too (MLflow's own run/experiment relationship cascades a hard delete onto
every run it still owns) and reported in `failed_experiments` instead, even when the experiment's
own hard-delete would otherwise have succeeded.

Query parameters interact as follows:
- Neither `run_ids` nor `experiment_ids` (an "empty trash" call): every deleted run and every
  deleted experiment older than `older_than` (default: all of them) is a candidate.
- `experiment_ids` given: those experiments and all of their runs are candidates, in addition to
  any `run_ids` also given.
- `run_ids` given without `experiment_ids`: **only** those runs are touched. No other trashed
  experiment, or any run other than the ones named, is read or deleted.

---

## Webhook Management

Base path: `/oidc/webhook`

All webhook endpoints require **admin** permissions.

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/oidc/webhook` | Create a webhook |
| GET | `/oidc/webhook` | List webhooks. Query: `max_results`, `page_token` |
| GET | `/oidc/webhook/{webhook_id}` | Get webhook details |
| PUT | `/oidc/webhook/{webhook_id}` | Update a webhook |
| DELETE | `/oidc/webhook/{webhook_id}` | Delete a webhook |
| POST | `/oidc/webhook/{webhook_id}/test` | Send a test event to the webhook |

**`POST /oidc/webhook` request:**
```json
{
  "url": "https://hooks.example.com/webhook",
  "events": ["MODEL_VERSION_CREATED", "MODEL_VERSION_TRANSITIONED_STAGE"],
  "description": "Notify on model promotion"
}
```

When workspaces are enabled, webhooks are automatically scoped to the active workspace.

---

## Workspace Endpoints

These endpoints are only available when `MLFLOW_ENABLE_WORKSPACES=true`.

### Workspace CRUD (MLflow Native)

Workspace lifecycle is handled by MLflow's native workspace API. The auth plugin enforces permission checks via `before_request` / `after_request` hooks.

Base path: `/api/3.0/mlflow/workspaces`

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | `/api/3.0/mlflow/workspaces` | Admin | Create workspace |
| GET | `/api/3.0/mlflow/workspaces` | Authenticated | List workspaces (filtered by permission) |
| GET | `/api/3.0/mlflow/workspaces/{workspace_name}` | Workspace READ | Get workspace details |
| PATCH | `/api/3.0/mlflow/workspaces/{workspace_name}` | Workspace MANAGE | Update workspace |
| DELETE | `/api/3.0/mlflow/workspaces/{workspace_name}` | Workspace MANAGE | Delete workspace |

### Workspace User Permissions

Base path: `/api/3.0/mlflow/permissions/workspaces/{workspace}`

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `.../users` | Workspace READ | List user permissions for workspace |
| POST | `.../users` | Workspace MANAGE | Grant user workspace permission |
| PATCH | `.../users/{username}` | Workspace MANAGE | Update user workspace permission |
| DELETE | `.../users/{username}` | Workspace MANAGE | Revoke user workspace permission |

### Workspace Group Permissions

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `.../groups` | Workspace READ | List group permissions for workspace |
| POST | `.../groups` | Workspace MANAGE | Grant group workspace permission |
| PATCH | `.../groups/{group_name}` | Workspace MANAGE | Update group workspace permission |
| DELETE | `.../groups/{group_name}` | Workspace MANAGE | Revoke group workspace permission |

### Workspace Regex Permissions (Admin Only)

Base path: `/api/3.0/mlflow/permissions/workspaces/regex`

| Method | Path | Purpose |
|--------|------|---------|
| POST | `.../regex/user` | Create user regex workspace permission |
| GET | `.../regex/user` | List user regex workspace permissions |
| PATCH | `.../regex/user/{id}` | Update user regex workspace permission |
| DELETE | `.../regex/user/{id}` | Delete user regex workspace permission |
| POST | `.../regex/group` | Create group regex workspace permission |
| GET | `.../regex/group` | List group regex workspace permissions |
| PATCH | `.../regex/group/{id}` | Update group regex workspace permission |
| DELETE | `.../regex/group/{id}` | Delete group regex workspace permission |

---

## SCIM

SCIM 2.0 provisioning and the lifecycle endpoints the admin UI uses. See
[SCIM Provisioning](scim) for behaviour.

### SCIM 2.0 endpoint

Base path: `/scim/v2`. It accepts **only** a SCIM bearer token (`Authorization: Bearer scim_...`).
Sessions, user tokens and OIDC tokens are refused with `401` and `WWW-Authenticate: Bearer`.
Repeated failures from one client IP get `429`. A write the ownership guard refuses gets
`409 mutability`.
Responses use `application/scim+json`, and errors use the RFC 7644 error schema.

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/scim/v2/ServiceProviderConfig` | Capabilities |
| GET | `/scim/v2/ResourceTypes`, `/scim/v2/ResourceTypes/{User,Group}` | Resource types |
| GET | `/scim/v2/Schemas`, `/scim/v2/Schemas/{urn}` | User and Group schemas |
| GET | `/scim/v2/Users` | List users; `filter=userName eq "..."` or `externalId eq "..."`, `startIndex`, `count` |
| POST | `/scim/v2/Users` | Provision a user |
| GET | `/scim/v2/Users/{id}` | Get a user (`id` is the username; an `externalId` does not resolve, use the filter) |
| PUT | `/scim/v2/Users/{id}` | Replace a user |
| PATCH | `/scim/v2/Users/{id}` | Modify a user; `active: false` deprovisions |
| DELETE | `/scim/v2/Users/{id}` | Hard-delete a user |
| GET | `/scim/v2/Groups` | List groups; `filter=displayName eq "..."` or `externalId eq "..."`, `startIndex`, `count`, `excludedAttributes=members` |
| POST | `/scim/v2/Groups` | Provision a group, optionally with members |
| GET | `/scim/v2/Groups/{id}` | Get a group (`id` is the group name) |
| PUT | `/scim/v2/Groups/{id}` | Replace a group; `members` replaces SCIM's membership (Okta) |
| PATCH | `/scim/v2/Groups/{id}` | Add/remove members, including `members[value eq "..."]` (Entra) |
| DELETE | `/scim/v2/Groups/{id}` | Delete a group, its memberships and its grants |

### SCIM token administration

Base path: `/api/2.0/mlflow/scim/tokens`. All endpoints are admin-only.

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/2.0/mlflow/scim/tokens` | List tokens (no hashes, no plaintexts) |
| POST | `/api/2.0/mlflow/scim/tokens` | Issue a token. Body `{"name": str, "expires_at": ISO-8601?}`. Returns `201` with `token` (plaintext, shown once) |
| POST | `/api/2.0/mlflow/scim/tokens/{id}/rotate` | Issue a replacement (`201`, with `token` and `replaces`); the old token expires after the overlap window |
| DELETE | `/api/2.0/mlflow/scim/tokens/{id}` | Revoke immediately |

Token object:

```json
{
  "id": 1,
  "name": "entra-prod",
  "token_prefix": "3f9a0c1b",
  "created_at": "2026-09-22T10:00:00+00:00",
  "created_by": "admin@example.com",
  "last_used_at": "2026-09-22T10:05:00+00:00",
  "expires_at": null,
  "revoked_at": null,
  "active": true
}
```

### Provisioning status and activity

Admin-only. See [Provisioning status and activity](scim#provisioning-status-and-activity) for what
is recorded.

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/2.0/mlflow/scim/status` | Provisioning health, overall and per token |
| GET | `/api/2.0/mlflow/scim/activity` | Recorded SCIM requests, newest first. Query: `limit` (1 to 200, default 50), `before` (an activity `id`: only older rows), `outcome` (`ok`, `client_error`, `server_error`, `auth_failed`; anything else is `400`), `token_id` |

**`GET /api/2.0/mlflow/scim/status` response:**
```json
{
  "provisioning_healthy": true,
  "last_success_at": "2026-09-23T10:05:00+00:00",
  "last_error_at": "2026-09-23T09:00:00+00:00",
  "last_error": "uniqueness: User 'alice@example.com' already exists",
  "requests_24h": 120,
  "errors_24h": 2,
  "auth_failures_24h": 1,
  "last_auth_failure_at": "2026-09-23T08:00:00+00:00",
  "healthy_window_seconds": 86400,
  "retention_days": 30,
  "tokens": [
    {
      "token_id": 1,
      "name": "entra-prod",
      "active": true,
      "last_used_at": "2026-09-23T10:05:00+00:00",
      "last_success_at": "2026-09-23T10:05:00+00:00",
      "last_error_at": "2026-09-23T09:00:00+00:00",
      "last_error": "uniqueness: User 'alice@example.com' already exists",
      "last_error_status": 409,
      "requests_24h": 119,
      "errors_24h": 1
    }
  ]
}
```

`provisioning_healthy` is `null` when SCIM has never been used.

**`GET /api/2.0/mlflow/scim/activity` response.** `next_before` is the value to pass as `before`
for the next page, or `null` when this page was the last:
```json
{
  "activity": [
    {
      "id": 42,
      "at": "2026-09-23T10:05:00+00:00",
      "token_id": 1,
      "token_name": "entra-prod",
      "method": "PATCH",
      "path": "/Users/{user_id}",
      "resource_id": "alice@example.com",
      "status": 200,
      "outcome": "ok",
      "error": null,
      "duration_ms": 12
    }
  ],
  "next_before": null
}
```

### User and group lifecycle state

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/api/2.0/mlflow/users/details` | Admin | Users with lifecycle state. Optional `service=true\|false` filter; omit it for both |
| PATCH | `/api/2.0/mlflow/users/{username}/active` | Admin | Deactivate or reactivate a user |
| GET | `/api/2.0/mlflow/users/{username}/sessions` | Admin | The user's live sessions |
| DELETE | `/api/2.0/mlflow/users/{username}/sessions/{pk}` | Admin | Revoke one of the user's sessions |
| DELETE | `/api/2.0/mlflow/users/{username}/sessions` | Admin | Revoke all of the user's sessions |
| GET | `/api/2.0/mlflow/permissions/groups/details` | Admin | Groups with external id and member count |

`GET /api/2.0/mlflow/users` and `GET /api/2.0/mlflow/permissions/groups` are unchanged and still
return `string[]`.

**`GET /api/2.0/mlflow/users/details` response** (ordered by creation). `PATCH .../active`
returns one such object:
```json
[
  {
    "username": "alice@example.com",
    "display_name": "Alice",
    "is_admin": false,
    "is_service_account": false,
    "active": true,
    "managed_by": "scim"
  }
]
```

**`PATCH /api/2.0/mlflow/users/{username}/active` request:**
```json
{"active": false, "admin_override": false}
```

`admin_override` is the break-glass flag for a user whose row another source owns under
`MANAGED_BY_ENFORCEMENT=enforce`. The override is always audited. Responses:

- `404` if there is no such user.
- `409` if the ownership guard refuses the change, or it would leave no active administrator.
- `403` if the caller is not an administrator.

**`DELETE /api/2.0/mlflow/users` request:**
```json
{"username": "alice@example.com", "admin_override": false}
```

The hard delete goes through the same ownership guard. `admin_override` is optional and
defaults to `false`. Under `enforce`, deleting a user whose row another source owns is refused
with `409` and audited as `user.ownership_conflict` (`detail.operation = "delete"`), unless
`admin_override` is `true`. The override is always audited.

**`GET /api/2.0/mlflow/users/{username}/sessions` response** (newest first, `Cache-Control:
no-store`):
```json
{
  "sessions": [
    {
      "pk": 17,
      "session_id_prefix": "Xk3v9QpA",
      "provider_id": "default",
      "created_at": "2026-09-23T08:00:00+00:00",
      "last_seen_at": null,
      "expires_at": "2026-09-23T16:00:00+00:00"
    }
  ]
}
```

The full session id is a bearer credential and is never returned. `session_id_prefix` tells
sessions apart; `pk` addresses one for `DELETE`. `last_seen_at` is `null` unless something records
it; the per-request authentication path deliberately does not write to the session row.

Both `DELETE`s return `{"revoked": <count>}` and emit `session.revoked` with
`detail.source = "admin"`. The session stops working on its next request. The account, its grants
and its access token are unchanged. Responses:

- `404` for an unknown user, or a `pk` that is not a live session of **this** user. Another user's
  session reads exactly like one that does not exist, and is not revoked.
- `403` if the caller is not an administrator.

**`PATCH /api/2.0/mlflow/users/ownership` request** (admin, break glass):
```json
{"username": "alice@example.com", "managed_by": "manual", "memberships": false}
```

This sets the user row's `managed_by` to `manual`, `scim`, `oidc:<id>` or `saml:<id>`. With
`"memberships": true` it also hands every group membership of the user to the new owner, in the
same transaction: if either half fails, nothing changes, the response is `500`, and a
`user.ownership_set` event with `status: "error"` is recorded. The response then lists the memberships that changed as
`"memberships": [{"group": "...", "from": "..."}]`. The change is audited as `user.ownership_set`.
See [Row ownership](configuration#group-membership).

**`GET /api/2.0/mlflow/permissions/groups/details` response** (ordered by name):
```json
[{"group_name": "data-team", "external_id": null, "member_count": 3}]
```

Groups have no `managed_by` of their own; ownership is recorded per membership.

---

## Admin UI

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/oidc/ui/config.json` | Authenticated | Runtime configuration for the React SPA |
| GET | `/oidc/ui/` | Public | Serve the admin UI (React SPA) |
| GET | `/oidc/ui/{path}` | Public | Serve static files or SPA fallback |

---

## Error Responses

All API errors follow this format:

```json
{
  "error_code": "RESOURCE_DOES_NOT_EXIST",
  "message": "User 'unknown@example.com' not found"
}
```

Common HTTP status codes:

| Status | Meaning |
|--------|---------|
| 401 | Authentication required (no valid credentials) |
| 403 | Forbidden (authenticated but insufficient permissions) |
| 404 | Resource not found |
| 409 | Conflict (resource already exists) |
| 503 | Service unavailable (health check failure) |
