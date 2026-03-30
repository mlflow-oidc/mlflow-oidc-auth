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

**Repository Explosion**
- Issue: 26+ repository files in `mlflow_oidc_auth/repository/` follow near-identical patterns (get, list, create, update, delete with SQLAlchemy sessions). Most are under 100 lines with trivial logic.
- Files: `mlflow_oidc_auth/repository/` (entire directory)
- Impact: Each new permission type spawns 2-4 new repository files. File count grows linearly with resource types.
- Fix approach: Consider a generic repository base class parameterized by model type, or consolidate related repositories (e.g., all gateway repositories into one).

**Dual Framework Architecture**
- Issue: The application runs both FastAPI and Flask simultaneously, with a complex bridge layer to pass authentication context from FastAPI middleware to Flask request handlers via WSGI environ variables.
- Files: `mlflow_oidc_auth/app.py`, `mlflow_oidc_auth/bridge/user.py`, `mlflow_oidc_auth/middleware/auth_aware_wsgi_middleware.py`
- Impact: Two separate request lifecycles, two sets of middleware, two error handling strategies. New developers must understand both frameworks and their interaction.
- Fix approach: This is architectural and likely intentional (MLflow uses Flask internally). Document the boundary clearly. Long-term, advocate for MLflow to expose extension points that don't require WSGI wrapping.


## Fragile Areas

**Flask Before/After Request Hooks**
- Files: `mlflow_oidc_auth/hooks/before_request.py` (567 lines), `mlflow_oidc_auth/hooks/after_request.py` (663 lines)
- Why fragile: These hooks match request paths using string patterns to determine which validator to call. Any change to MLflow's REST API paths requires updating the route matching logic.
- Safe modification: Add integration tests that verify route patterns match actual MLflow endpoints for the supported version range.
- Test coverage: Route matching patterns are not tested.

## Scaling Limits

**SQLite Default Database**
- Current capacity: Single-writer, file-based database suitable for development/small deployments.
- Limit: SQLite does not support concurrent writes. Under moderate load with multiple replicas, write contention causes `database is locked` errors.
- Scaling path: Configure PostgreSQL or MySQL via the `OIDC_AUTH_DATABASE_URI` environment variable. The codebase uses SQLAlchemy, so switching databases requires only a connection string change.

## Dependencies at Risk

**Tight MLflow Version Coupling**
- Risk: Pinned to `mlflow>=3.10.0,<4`. The codebase depends on MLflow private/internal APIs: `_get_tracking_store`, `_get_managed_session_maker`, `_get_graphql_auth_middleware`, protobuf message types, and Flask route patterns. Any MLflow major (or even minor) version change could break multiple integration points.
- Files: `pyproject.toml` (dependency spec), `mlflow_oidc_auth/graphql/patch.py` (monkey-patching), `mlflow_oidc_auth/hooks/before_request.py` (route patterns), `mlflow_oidc_auth/hooks/after_request.py` (response parsing)
- Impact: MLflow upgrades require extensive testing of all hook/bridge/patch code.
- Migration plan: Track MLflow changelogs proactively. Maintain an integration test suite that runs against each supported MLflow version. Advocate upstream for stable plugin APIs.

## Missing Critical Features

**No Rate Limiting**
- Problem: No rate limiting on any endpoint, including authentication endpoints (login, token validation, basic auth).
- Blocks: Protection against brute-force attacks on basic auth credentials and abuse of the OIDC token exchange flow.


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

*Concerns audit: 2026-03-23 (bug fix history updated: 2026-03-27, SonarCloud fixes added: 2026-03-27, top-10 concerns resolved: 2026-03-27, batch-2 concerns resolved: 2026-03-27)*
