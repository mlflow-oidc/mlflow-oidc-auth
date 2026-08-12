# Configuration Reference

The application is configured through environment variables, `.env` files, or pluggable secret providers (AWS, Azure, Vault, Kubernetes). See [Configuration Providers](configuration-providers) for cloud-specific setup.

## Environment Variables

### OIDC Authentication

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `OIDC_DISCOVERY_URL` | String | *Required* | OIDC discovery endpoint URL (e.g., `https://idp.example.com/.well-known/openid-configuration`) |
| `OIDC_CLIENT_ID` | String | *Required* | Client ID registered with your OIDC provider |
| `OIDC_CLIENT_SECRET` | String | *Required* | Client secret for your OIDC application |
| `OIDC_REDIRECT_URI` | String | Auto-detected | Redirect URI for the OIDC callback (`/callback`). If not set, calculated dynamically from proxy headers, which works correctly behind reverse proxies |
| `OIDC_SCOPE` | String | `openid,email,profile` | Comma-separated list of OIDC scopes to request |
| `OIDC_AUDIENCE` | String | None | Expected JWT `aud` claim value (e.g., your client ID or API identifier). When set, bearer tokens are rejected if the `aud` claim doesn't match. Recommended for production to prevent token confusion attacks |
| `OIDC_ISSUER` | String | None | Expected JWT `iss` claim value. When set, tokens whose issuer does not match are rejected. Also a required precondition for `OIDC_PROVISION_ON_BEARER_AUTH` |
| `OIDC_PROVISION_ON_BEARER_AUTH` | Boolean | `false` | Auto-create a permission record on first bearer-token authentication for API-first users who never logged in via the browser (fixes ownerless resources, issue #262). Requires **both** `OIDC_AUDIENCE` and `OIDC_ISSUER` set. Provisioned users are **non-admin** and must pass the same group-authorization gate as interactive login. **Note:** unlike browser login (which reads groups from the userinfo endpoint), the bearer path resolves groups from the token itself — the access token must carry the groups claim (or `OIDC_GROUP_DETECTION_PLUGIN` must accept the presented JWT), otherwise the user fails the group gate and is not provisioned (they continue to be denied creation, never silently over-granted) |
| `OIDC_TRUST_BEARER_GROUP_CLAIMS` | Boolean | `false` | Whether a bearer token may confer **admin** (via `OIDC_ADMIN_GROUP_NAME` membership in its group claim). Default false: admin is never granted from a token. Only enable if the IdP — not the token subject — controls the groups claim on audience-restricted tokens |
| `OIDC_PROVIDER_DISPLAY_NAME` | String | `Login with OIDC` | Display name shown on the login page button |
| `OIDC_GROUPS_ATTRIBUTE` | String | `groups` | Attribute name in the ID token that contains the user's group memberships |
| `OIDC_USERNAME_FIELD` | String | `email,preferred_username` | Comma-separated list of userinfo/token claim names tried in order to resolve the login identity. The first non-empty string field wins and is lowercased. Use this when your IdP shouldn't be identified by email (e.g. it may be reassigned) or when you want a stable claim like `sub` instead. **Note:** leaving this effectively empty logs a startup warning — no login or bearer-token authentication could ever resolve a username |
| `OIDC_DISPLAY_NAME_FIELD` | String | `name` | Comma-separated list of userinfo/token claim names tried in order to resolve the human-readable display name shown in the UI. The first non-empty string field wins. **Note:** leaving this effectively empty logs a startup warning — no login could ever resolve a display name |
| `OIDC_SESSION_EXPIRY_LEEWAY_SECONDS` | Integer | `30` | Clock-skew leeway applied to the IdP-issued token expiry. Sessions are rejected once `now >= expires_at - leeway`, forcing the user back through the OIDC login flow so IdP-side changes (deactivation, group changes, MFA enrollment) take effect within the token's lifetime instead of waiting for the cookie TTL |
| `OIDC_USE_REFRESH_TOKEN` | Boolean | `false` | When `true`, request `offline_access` and persist the refresh token in the session so expired sessions are silently refreshed against the IdP without forcing a visible login. Disabled by default because many enterprises require additional approval for `offline_access` and because refresh tokens are persisted in the signed (but not encrypted) session cookie |

### Group and Access Control

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `OIDC_GROUP_NAME` | String | `mlflow` | Comma-separated list of allowed groups. Users must belong to at least one of these groups (or an admin group) to log in. **Note:** leaving this effectively empty logs a startup warning — no user could ever be recognized as a member of an allowed group |
| `OIDC_ADMIN_GROUP_NAME` | String | `mlflow-admin` | Comma-separated list of admin groups. Members have full admin privileges and bypass all permission checks. **Note:** leaving this effectively empty logs a startup warning — no user could ever be granted admin access via group membership |
| `OIDC_GROUP_DETECTION_PLUGIN` | String | None | Python module path for a custom group detection plugin. When set, groups are extracted from the access token using this plugin instead of the ID token's groups attribute |

### Permissions

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `DEFAULT_MLFLOW_PERMISSION` | String | `MANAGE` | Default permission level when no explicit permission is found. Options: `READ`, `USE`, `EDIT`, `MANAGE`, `NO_PERMISSIONS`. See [Permissions](permissions) |
| `PERMISSION_SOURCE_ORDER` | String | `user,group,regex,group-regex` | Comma-separated order for evaluating permission sources. The first source with a matching permission wins. See [Permissions](permissions#permission-source-order) |
| `RESTRICT_RESOURCE_CREATION` | Boolean | `false` | When enabled, require EDIT+ permission (via name regex / group-regex, with a workspace fallback) to create experiments and registered models. **Note:** ineffective on its own if `DEFAULT_MLFLOW_PERMISSION` is left at the default `MANAGE` — lower it below `EDIT` (or use workspaces) to actually restrict creation. Off by default, matching upstream MLflow. See [Resource Creation Authorization](permissions#resource-creation-authorization) |

### Database

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `OIDC_USERS_DB_URI` | String | `sqlite:///auth.db` | Database connection URI for user/permission storage. Supports SQLite, PostgreSQL, MySQL, and any SQLAlchemy-compatible database |
| `OIDC_ALEMBIC_VERSION_TABLE` | String | `alembic_version` | Alembic migration version table name. Change this if you need to avoid conflicts with other Alembic-managed schemas in the same database |

### Security

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `SECRET_KEY` | String | Auto-generated | Secret key used to sign session cookies. **All replicas must share the same value** in multi-instance deployments. If not set, a random key is generated on startup and a warning is logged — sessions will not survive restarts or work across replicas |
| `TRUSTED_PROXIES` | String (CSV) | Empty (trust all) | Comma-separated list of trusted proxy IP addresses or CIDR ranges (e.g., `10.0.0.0/8,172.16.0.0/12`). When configured, `X-Forwarded-*` headers from untrusted sources are ignored. When empty, all proxy headers are trusted for backward compatibility |
| `AUTOMATIC_LOGIN_REDIRECT` | Boolean | `false` | When `true`, unauthenticated browser requests are automatically redirected to the OIDC login page instead of showing the login UI |

### UI Behavior

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `EXTEND_MLFLOW_MENU` | Boolean | `true` | Inject sign-in/sign-out links and permission management navigation into MLflow's built-in UI |
| `EXTEND_MLFLOW_REAUTH` | Boolean | `true` | Inject a small script into MLflow's UI that triggers a full page reload on any 401 response. Without this, an expired session leaves the SPA rendering empty pages until a manual force-reload, because React Router intercepts URL-bar navigations as soft routing |
| `DEFAULT_LANDING_PAGE_IS_PERMISSIONS` | Boolean | `true` | Use the permissions management page as the default landing page in the admin UI |

### Feature Flags

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `OIDC_GEN_AI_GATEWAY_ENABLED` | Boolean | `true` | Enable AI Gateway permission management in the admin UI and API. Disable if you don't use MLflow AI Gateway |
| `MLFLOW_ENABLE_WORKSPACES` | Boolean | `false` | Enable workspace (multi-tenant) support. Requires MLflow >=3.10. See [Workspaces](workspaces) |
| `ENABLE_API_DOCS` | Boolean | `true` | Enable OpenAPI documentation at `/openapi.json`, Swagger UI at `/docs`, and ReDoc at `/redoc` |

### Caching

The plugin uses TTL caches to avoid repeated database lookups on every request. Two independent caches exist: one for OIDC/JWT key material and one for permission resolution results.

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `OIDC_JWKS_CACHE_TTL_SECONDS` | Integer | `300` | Time-to-live (seconds) for the JWKS key set cache. The OIDC provider's signing keys are fetched once and cached for this duration. This is always a local in-process cache (not affected by `CACHE_BACKEND`) because JWKS data is identical across replicas |
| `OIDC_HTTP_TIMEOUT_SECONDS` | Integer | `10` | Timeout (seconds) applied to OIDC discovery and JWKS HTTP fetches. Set lower for faster failover when the IdP is unreachable; without a timeout a hung IdP can block request threads until the OS-level TCP timeout (~2 minutes), causing cascading auth failures |
| `OIDC_VERIFY_SSL` | Boolean | `true` | Verify the OIDC provider's TLS certificate on discovery, JWKS, and token requests. Only set to `false` for providers using self-signed certificates in a trusted network |
| `OIDC_CODE_CHALLENGE` | String | `S256` | PKCE code-challenge method for the authorization-code flow. `S256` (or `true`/`yes`/`on`/`1`), or `none`/`off`/`false`/`no`/`0` to disable. An unrecognised value warns and falls back to `S256`. See [PKCE](#pkce) |
| `MANAGED_BY_ENFORCEMENT` | String | `report` | What happens when one source writes a row another owns: `off`, `report` (audit only) or `enforce`. See [Row ownership](#row-ownership) |
| `PERMISSION_CACHE_TTL_SECONDS` | Integer | `30` | Time-to-live (seconds) for the permission resolution cache. Cached permission decisions expire after this duration. Lower values mean faster propagation of permission changes; higher values reduce database load |
| `CACHE_BACKEND` | String | `local` | Cache backend for permission and workspace caches. Options: `local` (in-process TTL cache) or `redis` (shared Redis instance). Use `redis` for multi-replica deployments where permission changes must propagate immediately across all replicas |
| `CACHE_REDIS_URL` | String | None | Redis connection URL. Required when `CACHE_BACKEND=redis`. Example: `redis://localhost:6379/0` or `redis://:password@redis-host:6379/1` |
| `CACHE_KEY_PREFIX` | String | `mlflow_oidc_auth:` | Key prefix for Redis cache entries. Useful when sharing a Redis instance with other applications |

> **Note:** Permission caches are automatically invalidated when permissions are created, updated, or deleted through the plugin's API. The TTL acts as a safety net, not the primary invalidation mechanism.

> **Compatibility:** Any Redis-protocol-compatible server works — including [Valkey](https://valkey.io/), [Dragonfly](https://www.dragonflydb.io/), and [KeyDB](https://docs.keydb.dev/). The plugin uses standard Redis commands (`GET`, `SET`, `DELETE`, `SCAN`) via the `redis-py` client library.

### Workspace Settings

These settings only apply when `MLFLOW_ENABLE_WORKSPACES=true`.

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `OIDC_WORKSPACE_DEFAULT_PERMISSION` | String | `NO_PERMISSIONS` | Permission level auto-assigned to users for workspaces detected during OIDC login |
| `OIDC_WORKSPACE_CLAIM_NAME` | String | `workspace` | OIDC token claim name used for workspace detection during login |
| `OIDC_WORKSPACE_DETECTION_PLUGIN` | String | None | Python module path for a custom workspace detection plugin. Used to extract workspace assignments from the OIDC token |
| `OIDC_WORKSPACE_REQUIRE_CREATION_CONTEXT` | Boolean | `false` | Reject workspace-gated create requests when no workspace context is present |
| `OIDC_WORKSPACE_DENY_DEFAULT_CREATION` | Boolean | `false` | Reject non-admin workspace-gated create requests that resolve to the `default` workspace, including requests that send no workspace context |
| `WORKSPACE_CACHE_MAX_SIZE` | Integer | `1024` | Maximum number of entries in the workspace permission cache |
| `WORKSPACE_CACHE_TTL_SECONDS` | Integer | `300` | Time-to-live (seconds) for workspace permission cache entries |

### Logging

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `LOG_LEVEL` | String | `INFO` | Application log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`) |
| `LOGGING_LOGGER_NAME` | String | `uvicorn` | Logger name to configure. Defaults to the uvicorn logger for FastAPI compatibility |

## Row ownership

`managed_by` records which source a user row belongs to — `manual`, `scim`, or
`oidc:<provider>`. `MANAGED_BY_ENFORCEMENT` decides what happens when a *different* source tries
to write it:

| Value | Behaviour |
|---|---|
| `off` | No evaluation at all |
| `report` | **Default.** The conflict is audited as `user.ownership_conflict`, and the write proceeds |
| `enforce` | The write is refused |

It defaults to `report` on purpose. The failure mode of a write guard is lockout, and lockout
cannot be repaired from inside a system that has just refused the write that would repair it —
so the telemetry exists a release before the enforcement does. Run on `report`, look at what
`user.ownership_conflict` events you actually get, then move to `enforce`.

An administrator action is permitted in every mode and always audited. That is deliberate: an
operator who cannot fix ownership from the admin UI is left with the database.

### Changing ownership

Ownership never changes implicitly — not at startup, not when a provider's configuration
changes, not as a side effect of a login. It is an operator action with a diff you read first:

```bash
mlflow-oidc db reconcile-ownership --url "$DB" --from-owner scim --set-owner manual
```

That prints the diff and changes nothing. Add `--apply` to write it, and `--journal FILE` to
record the prior ownership of every row it touches:

```bash
mlflow-oidc db reconcile-ownership --url "$DB" --from-owner scim --set-owner manual --apply --journal /tmp/ownership.json
mlflow-oidc db restore-ownership --url "$DB" --journal /tmp/ownership.json --apply
```

The dry-run diff and the applied diff come from the same query, so what you approve is what
runs. `restore-ownership` is also a dry run without `--apply`.

**This is the repair path when a source is turned off.** Point `--from-owner` at it and
`--set-owner` at `manual`, and the rows it used to own become editable again.

## PKCE

[PKCE](https://www.rfc-editor.org/rfc/rfc7636) is **enabled by default** (`S256`).

It binds the authorization code to a secret that only the login attempt that started the flow
knows, so a code intercepted on its way back — from a browser history entry, a proxy log, a
shared machine, a misconfigured redirect — cannot be exchanged for tokens by whoever intercepted
it. There is no cost to it for a provider that supports it, which is nearly all of them.

**This changed.** Earlier versions left PKCE off unless `OIDC_CODE_CHALLENGE` was set explicitly.
If your provider supports PKCE — Entra ID, Okta, Auth0, Keycloak, Google, and any provider
advertising `code_challenge_methods_supported` all do — nothing is required of you.

If your provider does **not** support it, disable it:

```bash
OIDC_CODE_CHALLENGE=none
```

`none`, `off`, `false`, `no`, `disabled`, `0` and an empty value all disable it, and doing so
logs a warning at startup — so a variable that renders blank from a Helm value or a compose file
cannot quietly turn PKCE off. `true`, `yes`, `on`, `enabled` and `1` all mean `S256`.

Any other value warns and falls back to `S256`, rather than being sent to the provider as a
challenge method it has never heard of. It falls back rather than refusing to start because this
configuration is read by the migration tooling too — a stale value would otherwise block
`mlflow-oidc db upgrade`, which is the upgrade this change asks you to perform.

**How a provider that cannot do PKCE reports itself:**

- If it advertises `code_challenge_methods_supported` in its discovery document and your method
  is not among them, login fails **before** redirecting, with a message naming the provider, the
  methods it does support, and this variable.
- If it advertises nothing (permitted by [RFC 8414](https://www.rfc-editor.org/rfc/rfc8414)) the
  login proceeds, and a rejected token exchange logs an `invalid_grant` line that names
  `OIDC_CODE_CHALLENGE=none` as the thing to try.

`plain` is **ignored, with a warning, in favour of `S256`**. RFC 7636 defines it, but the pinned
authlib emits a challenge for `S256` only, so a client configured for `plain` sends an
authorization request with no challenge at all — it reported PKCE as enabled while nothing was
bound to the code. If you have `OIDC_CODE_CHALLENGE=plain` set today, it was doing nothing; for
a provider that genuinely offers only `plain`, set `none` so the state is explicit.

> **Note:** with PKCE enabled, authlib logs the per-attempt code verifier at `DEBUG`. It is
> single-use and short-lived, but `LOG_LEVEL=DEBUG` is not a good idea in production for this
> reason among others.

## Sessions

Browser sessions are **server-side**: a row in the `auth_sessions` table of the auth database.
The cookie carries only an opaque identifier, so a session can be ended by the server rather
than merely forgotten by the browser.

- The identifier is resolved against the database on **every** request, uncached, so revoking a
  session takes effect on the next request — no TTL to wait out
- Deactivating or deleting a user revokes their live sessions immediately, and records a
  `session.revoked` audit event
- Logging out revokes the row. If revocation fails, logout returns **503** rather than
  reporting success, because a cleared cookie does not end a session that is still live
- The cookie is still signed with `SECRET_KEY` — all replicas **must** share the same key, and
  it must be set explicitly for sessions to survive a restart
- The cookie is signed but **not** encrypted; nothing secret belongs in it

**Session expiry is absolute, not rolling.** A session's lifetime is fixed at login to
`SESSION_COOKIE_MAX_AGE_SECONDS` (two weeks by default) and is not extended by activity, so a
continuously active user re-authenticates with the identity provider every two weeks. The
browser cookie's own `Max-Age` is refreshed on each response, but the server-side row is what
decides, and it is not. Lower the value to shorten the window; there is no setting that makes
it rolling.

**Sessions are not swept automatically.** Every login inserts a row and an expired one is simply
refused, so the table grows until an operator prunes it:

```bash
mlflow-oidc db prune-sessions --url postgresql://user:pass@host/auth_db
```

Add `--dry-run` to see the count without deleting. Revoked-but-unexpired rows are kept until
their expiry, so "was this session revoked, and when?" stays answerable. Running it from cron is
the expected deployment.

**Upgrading:** the session format changed in this release. Cookies issued by an earlier version
no longer authenticate — they carried the username directly, which is exactly what could not be
revoked — so every user logs in again once after the upgrade. No configuration change is needed.

Additional session cookie settings:

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `SESSION_COOKIE_NAME` | String | `session` | Session cookie name |
| `SESSION_COOKIE_MAX_AGE_SECONDS` | Integer | `1209600` (2 weeks) | Absolute session lifetime in seconds, fixed at login and not extended by activity. `0` makes the *cookie* last only as long as the browser session; the server-side session still expires after two weeks |
| `SESSION_COOKIE_SAMESITE` | String | `lax` | SameSite flag prevents the browser from sending session cookie along with cross-site requests |
| `SESSION_COOKIE_SECURE` | Boolean | `false` | Indicate that the "Secure" flag should be set (can be used with HTTPS only), set this to `true` in production to ensure the session cookie is only sent over HTTPS |

## MLflow Server Environment Variables

MLflow natively supports environment variables for server configuration. These are not managed by the plugin but are commonly used alongside it:

| CLI Parameter | Environment Variable | Description |
|--------------|---------------------|-------------|
| `--backend-store-uri` | `MLFLOW_BACKEND_STORE_URI` | Database URI for experiments, runs, models |
| `--registry-store-uri` | `MLFLOW_REGISTRY_STORE_URI` | Model registry URI (defaults to backend store) |
| `--default-artifact-root` | `MLFLOW_DEFAULT_ARTIFACT_ROOT` | Default artifact storage location |
| `--artifacts-destination` | `MLFLOW_ARTIFACTS_DESTINATION` | Proxied artifact storage destination |
| `--serve-artifacts` | `MLFLOW_SERVE_ARTIFACTS` | Enable artifact proxying |
| `--workers` | `MLFLOW_WORKERS` | Number of uvicorn workers |
| `--uvicorn-opts` | `MLFLOW_UVICORN_OPTS` | Additional uvicorn server options |
| `--gunicorn-opts` | `MLFLOW_GUNICORN_OPTS` | Additional gunicorn server options |

## Configuration Examples

### Minimal Development Setup

```bash
# .env file
OIDC_DISCOVERY_URL=https://your-idp.example.com/.well-known/openid-configuration
OIDC_CLIENT_ID=mlflow-dev
OIDC_CLIENT_SECRET=dev-secret
SECRET_KEY=dev-not-for-production
```

### Security-First Production Setup

```bash
# Deny all access by default — require explicit permission grants
DEFAULT_MLFLOW_PERMISSION=NO_PERMISSIONS

# Strict group requirements
OIDC_GROUP_NAME=mlflow-users,mlflow-data-scientists
OIDC_ADMIN_GROUP_NAME=mlflow-admins

# PostgreSQL backends
MLFLOW_BACKEND_STORE_URI=postgresql://mlflow:pass@db:5432/mlflow
OIDC_USERS_DB_URI=postgresql://mlflow:pass@db:5432/mlflow_auth

# Explicit secret key for multi-replica deployments
SECRET_KEY=your-random-64-char-hex-string

# Secure session cookies
SESSION_COOKIE_MAX_AGE_SECONDS=0
SESSION_COOKIE_SAMESITE=strict
SESSION_COOKIE_SECURE=true

# Disable API docs
ENABLE_API_DOCS=false

# Auto-redirect to OIDC login
AUTOMATIC_LOGIN_REDIRECT=true
```

### Multi-Tenant Workspace Setup

```bash
# Enable workspaces
MLFLOW_ENABLE_WORKSPACES=true

# New users get no workspace access by default
OIDC_WORKSPACE_DEFAULT_PERMISSION=NO_PERMISSIONS

# Detect workspace from OIDC token claim
OIDC_WORKSPACE_CLAIM_NAME=organization

# Cache workspace permissions (5 min TTL, 2048 max entries)
WORKSPACE_CACHE_MAX_SIZE=2048
WORKSPACE_CACHE_TTL_SECONDS=300

# Deny access to resources without explicit permissions
DEFAULT_MLFLOW_PERMISSION=NO_PERMISSIONS
```

### Group-Priority Permission Resolution

```bash
# Check group permissions before individual user permissions
PERMISSION_SOURCE_ORDER=group,user,group-regex,regex

# Read-only by default
DEFAULT_MLFLOW_PERMISSION=READ
```

### Multi-Replica with Redis Cache

```bash
# Shared cache backend for permission invalidation across replicas
CACHE_BACKEND=redis
CACHE_REDIS_URL=redis://redis-host:6379/0

# Short permission cache TTL for faster propagation
PERMISSION_CACHE_TTL_SECONDS=30

# JWKS cache (always local, 5 min default is fine)
OIDC_JWKS_CACHE_TTL_SECONDS=300

# JWT audience validation (recommended for production)
OIDC_AUDIENCE=my-mlflow-client-id

# Trusted proxy CIDR (if behind a load balancer)
TRUSTED_PROXIES=10.0.0.0/8,172.16.0.0/12

# All replicas must share the same secret key
SECRET_KEY=your-random-64-char-hex-string
```
