# Threat model: mlflow-oidc-auth

## What this project does

`mlflow-oidc-auth` (MLflow Access Control) is an authentication and authorization plugin for an
MLflow tracking server. It adds single sign-on (OIDC, SAML 2.0), SCIM provisioning, service
accounts, named access tokens, RBAC over users and groups, and per-resource permissions
(experiments, registered models, prompts, scorers, AI Gateway endpoints/secrets/model definitions,
MCP servers, workspaces).

**The core security property is multi-tenant isolation.** Several organizations share one MLflow
instance; each must see and change only what it was granted. A cross-tenant read is as serious as
a missing permission check: a list or search endpoint that forgets to filter its results is a
vulnerability, not a bug.

The plugin controls authentication and authorization only. It cannot change MLflow's behavior —
it sits in front of MLflow and decides whether a request reaches it, and filters what comes back.

### Architecture in one paragraph

A FastAPI (ASGI) app owns authentication and the permission API; MLflow's own Flask app is mounted
underneath it. Middleware, outermost first: Proxy headers → Session → WorkspaceContext → Auth →
Permission (`mlflow_oidc_auth/app.py`, `add_middleware_stack()`). Identity crosses into Flask as an
`AuthContext` in the ASGI scope, copied into the WSGI environ and read by
`mlflow_oidc_auth/bridge/user.py`. Flask-side authorization is `hooks/before_request.py` (maps each
MLflow route to a validator in `validators/`) and `hooks/after_request.py` (filters list/search
responses and auto-grants on creation). GraphQL is authorized in `graphql/`. Persistence is
SQLAlchemy (`sqlalchemy_store.py`, `repository/`, Alembic migrations in `db/migrations/`).

## Where untrusted input enters

Treat everything below as attacker-controlled unless stated otherwise.

- **Every HTTP request** to the server, from unauthenticated clients and from authenticated users
  of any tenant. Paths, query strings, headers, bodies, cookies.
- **Credentials**, tried in this order by `middleware/auth_middleware.py`:
  - `Authorization: Basic` — username + named access token (prefix lookup + password hash).
  - `Authorization: Bearer` JWT — validated against one or more configured IdPs' JWKS
    (`auth.py`, `oauth.py`, `provider_registry.py`, `identity_resolution.py`); also Kubernetes
    service-account tokens (`kubernetes.py`).
  - Session cookie — signed with `SECRET_KEY`; refresh/ID tokens held encrypted server-side
    (`session/`).
- **IdP responses**: OIDC authorization responses and ID tokens at `/callback`
  (`authorization_response.py`), SAML responses at the SAML ACS (`saml.py`, `routers/saml.py`).
  Claims — username, email, groups — are attacker-influenced in multi-IdP setups.
- **SCIM** (`/scim/v2`, `routers/scim.py`): authenticated by a SCIM bearer token, but the payloads
  (users, groups, membership patches, filters) are untrusted.
- **Forwarded headers** (`X-Forwarded-*`, `X-Real-IP`, forwarded prefix): honoured only from
  `TRUSTED_PROXIES`; from anyone else they are untrusted (`middleware/proxy_headers_middleware.py`).
- **Login redirect targets** (`next` / return-to parameters): open-redirect surface.
- **Regex permissions**: admins and resource managers can store regular expressions matched
  against resource names (ReDoS surface; see `docs/permissions.md#regex-safety-redos-protection`).
- **AI Gateway / MCP traffic** proxied through MLflow: client headers must not be forwarded to
  upstream providers.
- **The admin UI** (`web-react/`, React + TypeScript, built into `mlflow_oidc_auth/ui/`): renders
  user-, group-, and resource names that other tenants control (stored XSS surface). Uses
  DOMPurify where HTML is rendered.

Trusted: the operator's configuration (environment variables, `AUTH_PROVIDERS` JSON, config
providers for AWS/Azure/Vault), the database, the IdP's signing keys, and MLflow itself.

## Components that matter most

1. Authentication: `middleware/auth_middleware.py`, `auth.py`, `oauth.py`, `saml.py`,
   `authorization_response.py`, `identity_resolution.py`, `provider_registry.py`, `kubernetes.py`,
   `session/`, `user.py`, token issuance in `routers/users.py`.
2. Route coverage and path handling: `hooks/before_request.py`, `middleware/route_path.py`,
   `middleware/fastapi_permission_middleware.py`, `middleware/proxy_headers_middleware.py`,
   the unprotected-route list. **An MLflow route with no validator is an unauthorized route.**
   Path-normalisation, prefix, method (HEAD/OPTIONS), and trailing-slash tricks that reach a
   handler without its check are high value.
3. Authorization decisions: `permissions.py`, `validators/`, `dependencies.py`,
   `workspace_rules.py`, `ownership.py`, `graphql/`, every router under `routers/`.
4. Response filtering and auto-grant: `hooks/after_request.py`.
5. SCIM and provisioning: `routers/scim.py`, `provisioning_policy.py`, `group_patterns.py`.
6. Admin UI (`web-react/src/`) — XSS, CSRF-relevant calls.

Less important but in scope: `cache/`, `config_providers/`, `audit.py`, migrations.

## Security invariants (a violation of any is a finding)

- **Deny by default.** No grant means no access. No fallback may grant on error, exception, or an
  unknown resource type.
- A user of workspace/tenant A cannot read, list, search, modify, or learn the existence of
  resources in workspace B without a grant there — including via search results, GraphQL,
  artifact paths, run → experiment indirection, model-version → model indirection, logged-model
  or trace IDs, or name-based grants that match across workspaces.
- A bearer token from one IdP cannot authenticate as an identity owned by another IdP, and cannot
  confer admin unless `OIDC_TRUST_BEARER_GROUP_CLAIMS` is enabled.
- A Basic-auth or non-interactive (workload) credential cannot mint a new access token.
- A SCIM token authenticates only under `/scim/v2` and nowhere else; nothing else authenticates
  under `/scim/v2`.
- Forwarded headers from an untrusted client change nothing.
- `MANAGE` on a workspace is deliberately enough to update or delete it — this is **not** a bug.
- Admins (members of `OIDC_ADMIN_GROUP_NAME`) bypass permission checks by design.

## How to exercise it

- Unit and security tests: `pytest -m "not integration and not e2e" mlflow_oidc_auth/tests`.
  Adversarial token/authorization-response suite: `mlflow_oidc_auth/tests/adversarial/` and
  `mlflow_oidc_auth/tests/test_token_algorithm_pinning.py`. `mlflow_oidc_auth/tests/jose_helpers.py`
  builds signed test JWTs and a local JWKS without any network.
- Running hook tests: run `mlflow_oidc_auth/tests/hooks/` **file by file**; running the whole
  directory in one process can hang.
- PostgreSQL 18 is installed in the image but stopped. To run the migration and concurrency tests
  against it instead of skipping them: `pg_ctlcluster 18 main start` and
  `export MLFLOW_OIDC_TEST_POSTGRES_URI=postgresql+psycopg2://mlflow_oidc@localhost:5432/mlflow_oidc_test`.
- Frontend: `cd web-react && yarn test`.
- There is no IdP offline, so a live server cannot complete an OIDC login. To drive real requests
  through the middleware stack, use an in-process FastAPI `TestClient` with Basic auth or a JWT from
  `jose_helpers.py`, as `test_token_algorithm_pinning.py`, `test_user_lifecycle.py` and
  `test_workspace_rules_api.py` do.
- The Keycloak e2e suite (`tox -e e2e`) needs a Keycloak server and is not available in the image.

## How we rate severity

- **Critical**: unauthenticated access to protected data or actions; authentication bypass;
  impersonating another user; becoming admin without being in the admin group; cross-tenant
  write or delete.
- **High**: an authenticated user reading another tenant's data (including names/metadata
  leaked through list, search, GraphQL, or error responses); privilege escalation within a tenant
  (e.g. `READ` → `EDIT`/`MANAGE`); stored XSS in the admin UI that runs as an admin; leaking
  tokens, secrets, or gateway credentials; open redirect that carries a session or token.
- **Medium**: privilege escalation that requires a non-default, unusual configuration; reflected
  XSS; login CSRF; open redirect without token leakage; ReDoS reachable by a non-admin;
  same-tenant information disclosure beyond the user's grant.
- **Low**: issues needing admin privileges or operator-controlled configuration to trigger;
  missing hardening headers; log noise; DoS from an authenticated admin.

The intended effect of an insecure, explicitly documented operator choice is at most Low: for
example, every user reaching unassigned resources in a non-workspace deployment that set
`DEFAULT_MLFLOW_PERMISSION` to a granting level (the default is `NO_PERMISSIONS`), or forwarded
headers being honoured when `TRUSTED_PROXIES` is `0.0.0.0/0`. This cap does not apply to anything
beyond that intended effect. Any cross-workspace effect, and any path that falls back to the
global default where a workspace-scoped decision should apply, is rated normally whatever
`DEFAULT_MLFLOW_PERMISSION` is set to.

## Out of scope / leave alone

- Vulnerabilities in MLflow itself that this plugin does not introduce or make worse. (Do report
  MLflow routes the plugin forgets to authorize — that is ours.)
- Lack of rate limiting on login and Basic auth (known, tracked).
- The auto-generated `SECRET_KEY` when none is configured (logged as a warning, documented).
- SQLite lacking row locks across processes (documented; PostgreSQL is the multi-replica backend).
- `mlflow_oidc_auth/ui/` is build output of `web-react/`; report issues against the `web-react/`
  sources. `scripts/`, `docs/`, and test fixtures are out of scope.
- Hard-coded credentials in tests and `scripts/e2e/` (e.g. Keycloak `admin`/`admin`) are local
  test fixtures, not secrets.

## How we would like reports

- One finding per report, with the exact request(s) or a pytest test that demonstrates it using the
  existing fixtures, and the file:line of the missing or wrong check.
- Patches should follow `AGENTS.md`: deny by default, add a negative test proving the access is now
  refused, never weaken an existing check to make a test pass, and do not add a database query to
  the per-request authentication path (`docs/performance-baseline.md`).
