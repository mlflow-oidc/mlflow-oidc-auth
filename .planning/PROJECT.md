# MLflow OIDC Auth — Organization Support

## What This Is

An MLflow authentication and authorization plugin (mlflow-oidc-auth) that adds OIDC-based login, RBAC with users/groups, and per-resource permission management to MLflow tracking servers. The project is adding multi-tenant organization support, aligning with MLflow 3.10's new organization features, to enable resource isolation across teams or external organizations sharing a single MLflow instance.

## Core Value

Multi-tenant resource isolation — organizations must be able to share an MLflow instance while each tenant sees only their own experiments, models, and resources, with no accidental data leakage between tenants.

## Requirements

### Validated

- ✓ OIDC authentication (login, logout, callback, session management) — existing
- ✓ Multi-method auth (OIDC, Basic Auth, Bearer Token/JWT, session cookies) — existing
- ✓ User management (create, update, list, admin roles) — existing
- ✓ Group management (create, assign users, group-level permissions) — existing
- ✓ Experiment permissions (user, group, regex, group-regex variants) — existing
- ✓ Registered model permissions (user, group, regex, group-regex variants) — existing
- ✓ Prompt permissions (user, group, regex, group-regex variants) — existing
- ✓ Scorer permissions (user, group, regex, group-regex variants) — existing
- ✓ Gateway endpoint permissions (user, group, regex, group-regex variants) — existing
- ✓ Gateway secret permissions (user, group, regex, group-regex variants) — existing
- ✓ Gateway model definition permissions (user, group, regex, group-regex variants) — existing
- ✓ Configurable permission resolution order (user → group → regex → group-regex) — existing
- ✓ Permission levels (READ, USE, EDIT, MANAGE, NO_PERMISSIONS) — existing
- ✓ Admin bypass for all permission checks — existing
- ✓ Auto-grant MANAGE on resource creation — existing
- ✓ Search result filtering based on user permissions — existing
- ✓ Cascade permission deletes on resource deletion — existing
- ✓ GraphQL authorization middleware — existing
- ✓ Pluggable config providers (AWS, Azure, Vault, K8s, env) — existing
- ✓ React SPA admin UI for managing permissions, users, groups — existing
- ✓ Alembic database migrations — existing
- ✓ MLflow plugin integration (mlflow server --app-name oidc-auth) — existing

### Active

- [ ] Research MLflow 3.10 organization support — deep dive into upstream code and docs
- [ ] Identify non-covered entities in the auth plugin (new MLflow 3.10 API endpoints/resources)
- [ ] Design organization model for mlflow-oidc-auth (entity, DB schema, API)
- [ ] Define org-to-group relationship (nested hierarchy vs orthogonal)
- [ ] Define resource isolation model (hard deny vs shareable across orgs)
- [ ] Define org identity source (OIDC claims, admin-managed, or hybrid)
- [ ] Implement organization support in backend (DB models, repositories, store, hooks, validators)
- [ ] Implement organization management UI in React frontend
- [ ] Database migration for organization tables
- [ ] Update permission resolution to incorporate org boundaries

### Out of Scope

- Per-org billing or usage metering — not an auth concern
- Multi-cluster/multi-instance federation — single instance scope only
- Org-specific MLflow configuration (e.g., artifact store per org) — MLflow core concern, not auth plugin

## Context

**Upstream trigger:** MLflow 3.10 (https://github.com/mlflow/mlflow/releases/tag/v3.10.0) introduced Organization Support. The upstream MLflow auth module at https://github.com/mlflow/mlflow/tree/master/mlflow/server/auth needs investigation to understand what hooks, models, and APIs were added.

**Existing architecture:** FastAPI wraps MLflow's Flask app via AuthAwareWSGIMiddleware. RBAC is enforced in Flask before_request hooks that map MLflow protobuf request classes to validator functions. Permission management is via FastAPI routers. The plugin has 7 resource types, each with 4 permission variants (user, group, regex, group-regex).

**Production deployments:** The plugin has existing production deployments with established users, groups, and permissions. Backward compatibility is important but breaking changes are acceptable with a major version bump.

**Research-first approach:** The exact scope of implementation depends on research findings. Key unknowns include what MLflow 3.10 actually exposes for orgs, what entities the current plugin doesn't intercept, and how orgs should integrate with the existing group/permission hierarchy.

**Multi-tenancy model:** Flexible — must support both internal teams and external organizations depending on deployment scenario.

## Constraints

- **Compatibility**: Must target MLflow >=3.10.0 — org features require 3.10 baseline
- **Production impact**: Existing deployments must have a clear migration path, even if major version bump
- **Tech stack**: Python/FastAPI/Flask/SQLAlchemy backend, React/TypeScript frontend — no new frameworks
- **Plugin boundary**: Can only control auth/authz — cannot modify MLflow core behavior
- **Research dependency**: Implementation scope gated on research findings about MLflow 3.10 internals

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Research-first approach before implementation | Too many unknowns about MLflow 3.10 org model | — Pending |
| Breaking changes OK with major version | Production deployments exist but org support is transformative enough to justify it | — Pending |
| Flexible tenancy model (internal + external) | Different deployments have different needs; don't lock into one model | — Pending |
| Deep dive upstream MLflow code + docs | Release notes alone won't reveal integration points for the auth plugin | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-03-23 after initialization*
