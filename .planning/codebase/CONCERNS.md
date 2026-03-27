# Codebase Concerns

**Analysis Date:** 2026-03-23

## Tech Debt

**God Object: `sqlalchemy_store.py` (1474 lines)**
- Issue: Single class with 150+ thin wrapper methods delegating to 34+ repository files. Acts as an unnecessary indirection layer between routers and repositories.
- Files: `mlflow_oidc_auth/sqlalchemy_store.py`
- Impact: Every new entity type requires adding multiple pass-through methods here. Increases maintenance burden and makes the codebase harder to navigate.
- Fix approach: Have routers depend on repositories directly (or use a thin service layer per domain). Gradually remove `SqlAlchemyStore` methods as repositories are injected via FastAPI dependencies.

**Massive Permission Router Files**
- Issue: `user_permissions.py` (2390 lines) and `group_permissions.py` (2205 lines) contain highly repetitive CRUD patterns for experiments, models, prompts, scorers, gateway endpoints, gateway secrets, and gateway model definitions. Each resource type duplicates the same create/read/update/delete endpoint structure.
- Files: `mlflow_oidc_auth/routers/user_permissions.py`, `mlflow_oidc_auth/routers/group_permissions.py`
- Impact: Adding a new resource type requires copying ~300 lines of boilerplate in each file. Bug fixes must be applied in multiple places.
- Fix approach: Extract a generic permission CRUD factory that generates endpoints for a given resource type. Example: `create_permission_routes(resource_name, repository, schema)`.

**~~Duplicated Permission Resolution Logic~~ (RESOLVED)**
- `utils/permissions.py` previously contained ~8 nearly identical functions for checking permissions across different resource types. Each followed the same pattern: check user permission → check group permission → check regex permission → check group regex permission.
- Fix: Refactored to use a registry-driven `resolve_permission()` function with `PERMISSION_REGISTRY` that parameterizes permission resolution by resource type.
- Files: `mlflow_oidc_auth/utils/permissions.py`

**Repository Explosion**
- Issue: 26+ repository files in `mlflow_oidc_auth/repository/` follow near-identical patterns (get, list, create, update, delete with SQLAlchemy sessions). Most are under 100 lines with trivial logic.
- Files: `mlflow_oidc_auth/repository/` (entire directory)
- Impact: Each new permission type spawns 2-4 new repository files. File count grows linearly with resource types.
- Fix approach: Consider a generic repository base class parameterized by model type, or consolidate related repositories (e.g., all gateway repositories into one).

**Duplicated Request Helper Logic**
- Issue: `get_model_id()` and `get_experiment_id()` have duplicated parameter extraction logic. A TODO comment at line 191 acknowledges this.
- Files: `mlflow_oidc_auth/utils/request_helpers.py:191-218`
- Impact: Minor — isolated duplication. But the TODO indicates recognized debt.
- Fix approach: Extract shared parameter resolution into a helper function as the TODO suggests.

**HTML Injection Hack**
- Issue: `hack.py` reads `menu.html` and injects it into MLflow's `index.html` via string replacement (`</head>` → `{menu_html}</head>`). The filename itself signals recognized tech debt.
- Files: `mlflow_oidc_auth/hack.py`
- Impact: Fragile — breaks if MLflow changes its HTML structure. No sanitization of injected content.
- Fix approach: Investigate MLflow plugin hooks or middleware-based injection. If string replacement must stay, add validation that the target marker exists.

**Global Module-Level Store Instantiation**
- Issue: `store.py` creates the database store instance at import time (lines 4-5), meaning the DB connection is established as a side effect of importing the module.
- Files: `mlflow_oidc_auth/store.py`
- Impact: Makes testing harder (can't mock before import), creates implicit initialization ordering, and prevents lazy connection setup.
- Fix approach: Use a factory function or FastAPI dependency injection to create the store instance lazily.

**Dual Framework Architecture**
- Issue: The application runs both FastAPI and Flask simultaneously, with a complex bridge layer to pass authentication context from FastAPI middleware to Flask request handlers via WSGI environ variables.
- Files: `mlflow_oidc_auth/app.py`, `mlflow_oidc_auth/bridge/user.py`, `mlflow_oidc_auth/middleware/auth_aware_wsgi_middleware.py`
- Impact: Two separate request lifecycles, two sets of middleware, two error handling strategies. New developers must understand both frameworks and their interaction.
- Fix approach: This is architectural and likely intentional (MLflow uses Flask internally). Document the boundary clearly. Long-term, advocate for MLflow to expose extension points that don't require WSGI wrapping.

**TODO/FIXME Comments**
- Issue: Active TODO comments indicating incomplete work.
- Files:
  - `mlflow_oidc_auth/validators/experiment.py:29` — TODO about experiment validation
  - `mlflow_oidc_auth/utils/request_helpers.py:191` — TODO about deduplicating get_model_id/get_experiment_id
  - `mlflow_oidc_auth/utils/permissions.py:421` — TODO about permission logic
- Impact: Minor individually, but indicate areas where shortcuts were taken.
- Fix approach: Triage and address each TODO. Convert to GitHub issues for tracking.

## Known Bugs

**~~User Deletion Missing Gateway Permission Cleanup~~ (RESOLVED)**
- When a user was deleted, their gateway endpoint/secret/model definition permissions and workspace permissions (both direct and regex) were NOT cleaned up, leaving orphaned records.
- Fix: Added cascade deletes for `SqlGatewayEndpointPermission`, `SqlGatewayEndpointRegexPermission`, `SqlGatewaySecretPermission`, `SqlGatewaySecretRegexPermission`, `SqlGatewayModelDefinitionPermission`, `SqlGatewayModelDefinitionRegexPermission`, `SqlWorkspacePermission`, `SqlWorkspaceRegexPermission`.
- Files: `mlflow_oidc_auth/repository/user.py`

**~~Gateway Validators Return True on Resolution Failure~~ (RESOLVED)**
- When a gateway resource name could not be resolved, validators returned `True` (allow access) instead of denying access — a fail-open pattern.
- Fix: Changed three model definition validators to return `False` (fail-closed) when the resource name cannot be resolved.
- Files: `mlflow_oidc_auth/validators/gateway.py`

**~~Log Injection in Workspace Logging~~ (RESOLVED)**
- Workspace CRUD router used f-string interpolation with user-controlled data (`body.name`, `workspace`, `username`) in logger calls, enabling log injection attacks. Workspace cache module passed unsanitized `username`/`workspace` to `%s` format params.
- Fix: Removed user-controlled data from `workspace_crud.py` log messages entirely. Added `_sanitize()` helper to `workspace_cache.py` stripping `\n`, `\r`, `\t` from all user-controlled log parameters.
- Files: `mlflow_oidc_auth/routers/workspace_crud.py`, `mlflow_oidc_auth/utils/workspace_cache.py`

**~~React Hooks Called After Early Returns~~ (RESOLVED)**
- Three workspace UI components had hooks called after conditional `return` statements (`if (!workspaces_enabled) return <Navigate />`), violating React Rules of Hooks and causing unpredictable behavior.
- Fix: Moved all hook calls above early returns in all three components.
- Files: `web-react/src/features/workspaces/workspace-detail-page.tsx`, `web-react/src/features/workspaces/workspaces-page.tsx`, `web-react/src/shared/components/workspace-picker.tsx`

**~~Workspace Picker Missing Keyboard Accessibility~~ (RESOLVED)**
- `<div role="option">` elements in workspace picker had click handlers but no keyboard event handlers or `tabIndex`, making them inaccessible to keyboard-only users.
- Fix: Added `tabIndex={0}` and `onKeyDown` handlers (Enter/Space) to all option elements.
- Files: `web-react/src/shared/components/workspace-picker.tsx`

**~~Webhook UI Not Refreshing on Workspace Change~~ (RESOLVED)**
- The `useWebhooks` hook used a manual `useCallback`/`useEffect` pattern instead of the shared `useApi` hook. This meant webhook data was fetched once on mount but never refetched when the active workspace changed, causing stale webhook data from the previous workspace to remain visible.
- Fix: Refactored `useWebhooks` to use `useApi<WebhookListResponse>(listWebhooks)`, which includes `selectedWorkspace` in its effect dependency array. Local status overrides preserved via a `localOverrides` Map.
- Files: `web-react/src/core/hooks/use-webhooks.ts`

**~~Workspace Permissions Showing as "regex" Kind~~ (RESOLVED)**
- The batch permission resolver in `utils/batch_permissions.py` was missing workspace fallback logic, causing workspace-derived permissions to be misidentified as "regex" kind in the UI.
- Fix: Added `_apply_workspace_fallback()` function, updated all three `resolve_*_permission_from_context()` functions, updated `PermissionKind` TypeScript type.
- Files: `mlflow_oidc_auth/utils/batch_permissions.py`, `web-react/src/shared/types/entity.ts`

**~~Workspace Change Not Reloading Permission Data~~ (RESOLVED)**
- React effect execution order race condition — child effects (`useApi`) ran before parent effects (`WorkspaceProvider`), so `getActiveWorkspace()` returned stale value.
- Fix: Update `_activeWorkspace` synchronously in `setSelectedWorkspace()` setter and `useState` initializer.
- Files: `web-react/src/shared/context/workspace-context.tsx`

**~~Webhooks 503 When Workspaces Enabled~~ (RESOLVED)**
- Webhook router used plain `SqlAlchemyStore` which rejects DBs with models in non-default workspaces via `_initialize_store_state()`.
- Fix: Use `WorkspaceAwareSqlAlchemyStore` when `config.MLFLOW_ENABLE_WORKSPACES` is true.
- Files: `mlflow_oidc_auth/routers/webhook.py`

## Security Considerations

**~~No JWKS/Discovery Caching~~ (RESOLVED)**
- Every bearer token validation previously triggered 2 HTTP requests to the OIDC provider (discovery document + JWKS endpoint).
- Fix: Added TTL-based caching for JWKS and discovery responses using `cachetools.TTLCache` with configurable TTL via `OIDC_JWKS_CACHE_TTL_SECONDS` (default 300s). Thread-safe via `threading.Lock`. On `BadSignatureError`, cache is force-refreshed to handle key rotation.
- Files: `mlflow_oidc_auth/auth.py`, `mlflow_oidc_auth/config.py`

**~~Session Secret Key Fallback~~ (RESOLVED)**
- If `SECRET_KEY` was not configured, a random key was generated at startup with no warning, causing session invalidation across replicas.
- Fix: Added `WARNING` log message on startup when the fallback random key is used, alerting operators to configure `SECRET_KEY` for multi-replica deployments.
- Files: `mlflow_oidc_auth/config.py`

**~~User-Supplied Regex Patterns (ReDoS Risk)~~ (RESOLVED)**
- Permission regex patterns stored in the database were evaluated with `re.match()` without complexity validation, allowing catastrophic backtracking patterns.
- Fix: Added ReDoS validation to `validate_regex()` in `repository/utils.py` — rejects patterns with nested quantifiers and limits pattern length to 1024 chars. All regex permission repositories inherit from base classes that already call `validate_regex()` on write paths.
- Files: `mlflow_oidc_auth/repository/utils.py`

**~~No JWT Audience Validation~~ (RESOLVED)**
- Bearer token validation did not validate the `aud` (audience) claim, accepting tokens issued for different applications by the same OIDC provider.
- Fix: Added `OIDC_AUDIENCE` configuration option. When set, audience is validated via `authlib.jose.jwt.decode()` `claims_options` with `payload.validate()`. When not set, audience validation is skipped (backward compatible).
- Files: `mlflow_oidc_auth/auth.py`, `mlflow_oidc_auth/config.py`

**~~Unconditional Proxy Header Trust~~ (RESOLVED)**
- `ProxyHeadersMiddleware` trusted all `X-Forwarded-For`, `X-Forwarded-Proto` headers unconditionally, allowing IP spoofing.
- Fix: Added `TRUSTED_PROXIES` configuration option accepting CIDR ranges. Only processes `X-Forwarded-*` headers from requests originating from trusted proxies. When not configured, all proxies are trusted (backward compatible).
- Files: `mlflow_oidc_auth/middleware/proxy_headers_middleware.py`, `mlflow_oidc_auth/config.py`

**~~Basic Auth Credentials Logged at Debug Level~~ (RESOLVED)**
- Authentication error exception messages could contain credential context and were logged at error/debug level using f-strings.
- Fix: Replaced all exception detail logging in auth methods with `type(e).__name__` only (logs exception class, not message). Removed user-controlled data from error return values in session auth methods.
- Files: `mlflow_oidc_auth/middleware/auth_middleware.py`

**~~Gateway Validators Fail Open~~ (RESOLVED)**
- When a gateway resource name could not be resolved, validators returned `True` (allow access).
- Fix: Changed to fail-closed — return `False` when a resource cannot be resolved.
- Files: `mlflow_oidc_auth/validators/gateway.py`

## Performance Bottlenecks

**~~No Permission Caching (Resource Permissions)~~ (RESOLVED)**
- Every incoming request previously triggered a multi-step permission resolution chain with database queries at each step and no caching.
- Fix: Added TTL-based caching at the `resolve_permission()` level using `cachetools.TTLCache`, configurable via `PERMISSION_CACHE_TTL_SECONDS` (default 30s). Cache is keyed by `(username, resource_type, resource_name)`. `invalidate_permission_cache()` and `flush_permission_cache()` functions provided for write-path invalidation.
- Files: `mlflow_oidc_auth/utils/permissions.py`, `mlflow_oidc_auth/config.py`

**Post-Fetch Search Result Filtering**
- Problem: `after_request.py` filters search results for experiments and registered models AFTER fetching them from MLflow. It iterates through results and re-fetches individually to check permissions, turning an O(1) search into O(n) permission checks.
- Files: `mlflow_oidc_auth/hooks/after_request.py` (`_filter_search_experiments`, `_filter_search_registered_models`)
- Cause: MLflow's search API doesn't support permission-aware queries, so filtering must happen post-fetch.
- Improvement path: Cache user permissions for the duration of the request to avoid repeated DB lookups. Consider pre-computing a user's accessible resource set for large deployments.

**~~JWKS Fetched on Every Token Validation~~ (RESOLVED)**
- Two HTTP round-trips per bearer token validation (discovery + JWKS) added latency to every API request using bearer tokens.
- Fix: Implemented TTL-based caching with force-refresh on `BadSignatureError` for key rotation handling. See JWKS/Discovery Caching entry in Security Considerations.
- Files: `mlflow_oidc_auth/auth.py`, `mlflow_oidc_auth/config.py`

**Eager Permission Loading on User List**
- Problem: The `list_users` endpoint calls `to_mlflow_entity()` for each user, which eagerly loads all permission relationships (experiment permissions, model permissions, etc.).
- Files: `mlflow_oidc_auth/routers/users.py:119`
- Cause: The entity conversion loads all relationships regardless of whether they're needed.
- Improvement path: Add a lightweight user listing that doesn't load permissions. Use lazy loading or separate endpoints for permission details.

## Fragile Areas

**MLflow HTML Injection (`hack.py`)**
- Files: `mlflow_oidc_auth/hack.py`
- Why fragile: Relies on MLflow's `index.html` containing a `</head>` tag in the expected position. Any change to MLflow's HTML structure breaks the injection.
- Safe modification: Test against the target MLflow version's HTML output before changing the injection logic.
- Test coverage: No tests for this file.

**Flask Before/After Request Hooks**
- Files: `mlflow_oidc_auth/hooks/before_request.py` (567 lines), `mlflow_oidc_auth/hooks/after_request.py` (663 lines)
- Why fragile: These hooks match request paths using string patterns to determine which validator to call. Any change to MLflow's REST API paths requires updating the route matching logic.
- Safe modification: Add integration tests that verify route patterns match actual MLflow endpoints for the supported version range.
- Test coverage: Route matching patterns are not tested.

**WSGI-to-ASGI Bridge**
- Files: `mlflow_oidc_auth/middleware/auth_aware_wsgi_middleware.py`, `mlflow_oidc_auth/bridge/user.py`
- Why fragile: Auth context is passed from FastAPI to Flask via WSGI environ variables (`mlflow_oidc_auth.username`, `mlflow_oidc_auth.is_admin`). If the middleware execution order changes or environ keys are modified, auth breaks silently.
- Safe modification: Use constants for environ keys. Add assertions in the Flask bridge that expected environ keys exist.
- Test coverage: No integration tests for the bridge.

**GraphQL Monkey-Patching**
- Files: `mlflow_oidc_auth/graphql/patch.py`
- Why fragile: Patches `mlflow.server.handlers._get_graphql_auth_middleware` — a private MLflow function. Private APIs can change without notice between MLflow versions.
- Safe modification: Pin MLflow version tightly and test the patch after every MLflow upgrade.
- Test coverage: No tests for the GraphQL patch.

## Scaling Limits

**SQLite Default Database**
- Current capacity: Single-writer, file-based database suitable for development/small deployments.
- Limit: SQLite does not support concurrent writes. Under moderate load with multiple replicas, write contention causes `database is locked` errors.
- Scaling path: Configure PostgreSQL or MySQL via the `OIDC_AUTH_DATABASE_URI` environment variable. The codebase uses SQLAlchemy, so switching databases requires only a connection string change.

**No Connection Pooling Configuration**
- Current capacity: Default SQLAlchemy connection pool settings.
- Limit: Under high concurrency, the default pool may be exhausted.
- Scaling path: Expose SQLAlchemy pool configuration (pool_size, max_overflow, pool_timeout) via environment variables.

## Dependencies at Risk

**Tight MLflow Version Coupling**
- Risk: Pinned to `mlflow>=3.10.0,<4`. The codebase depends on MLflow private/internal APIs: `_get_tracking_store`, `_get_managed_session_maker`, `_get_graphql_auth_middleware`, protobuf message types, and Flask route patterns. Any MLflow major (or even minor) version change could break multiple integration points.
- Files: `pyproject.toml` (dependency spec), `mlflow_oidc_auth/graphql/patch.py` (monkey-patching), `mlflow_oidc_auth/hooks/before_request.py` (route patterns), `mlflow_oidc_auth/hooks/after_request.py` (response parsing)
- Impact: MLflow upgrades require extensive testing of all hook/bridge/patch code.
- Migration plan: Track MLflow changelogs proactively. Maintain an integration test suite that runs against each supported MLflow version. Advocate upstream for stable plugin APIs.

**Frontend `react-router` in devDependencies**
- Risk: `react-router` is listed in `devDependencies` instead of `dependencies` in `web-react/package.json:47`. This works during development but would fail in production if the build process doesn't install devDependencies.
- Files: `web-react/package.json`
- Impact: Build failures in CI/CD environments that only install production dependencies.
- Migration plan: Move `react-router` to `dependencies`.

## Missing Critical Features

**No Rate Limiting**
- Problem: No rate limiting on any endpoint, including authentication endpoints (login, token validation, basic auth).
- Blocks: Protection against brute-force attacks on basic auth credentials and abuse of the OIDC token exchange flow.

**No Audit Logging**
- Problem: Permission changes (grant, revoke, modify) are not logged to an audit trail. Admin actions have no accountability record.
- Blocks: Compliance requirements, incident investigation, permission change tracking.

**~~No Health Check Endpoint~~ (RESOLVED)**
- Health check endpoints exist at `/health` (basic), `/health/ready` (readiness), `/health/live` (liveness), and `/health/startup` (startup probe).
- Implementation: `mlflow_oidc_auth/routers/health.py`

## Test Coverage Gaps

**Comprehensive Test Suite Exists**
- The Python backend has 2574+ tests across ~110 test files in `mlflow_oidc_auth/tests/`. Test types include unit tests, repository tests, router tests, middleware tests, hook tests, validator tests, and integration tests (Playwright-based).
- Files: `mlflow_oidc_auth/tests/` (entire directory)
- Coverage: Tracked via `coverage.py` and reported to SonarCloud.

**Frontend Tests Exist**
- The React frontend has 819+ tests across ~116 test files, co-located with source files. Uses Vitest with Testing Library.
- Files: `web-react/src/` (`.test.tsx` / `.test.ts` files)
- Coverage: Enforced at 80% thresholds (statements, branches, functions, lines).

**Areas with Remaining Gaps:**

---

*Concerns audit: 2026-03-23 (bug fix history updated: 2026-03-27, SonarCloud fixes added: 2026-03-27, top-10 concerns resolved: 2026-03-27)*
