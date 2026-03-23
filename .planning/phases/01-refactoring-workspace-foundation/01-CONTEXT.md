# Phase 1: Refactoring & Workspace Foundation - Context

**Gathered:** 2026-03-23
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase eliminates permission resolution copy-paste debt and establishes all workspace plumbing (feature flag, DB migration, context propagation, default workspace). After this phase:
- Permission resolution for all 7 resource types uses a single generic function
- Repository classes share a generic base class
- Workspace tables exist in the database
- Workspace context flows through the middleware bridge
- Feature flag gates all workspace behavior
- Existing deployments are unaffected (zero behavioral changes when flag is off)

**Requirements:** REFAC-01, REFAC-02, WSFND-01, WSFND-02, WSFND-03, WSFND-04, WSFND-05, WSFND-06

</domain>

<decisions>
## Implementation Decisions

### Permission Resolution Refactoring (REFAC-01)

- **Parameterized function approach** — A single `resolve_permission(resource_type, resource_id, username)` that uses a registry/mapping of resource types to store methods. The 8 `_permission_*_sources_config` functions become data entries in a dict keyed by resource type.
- **`PERMISSION_SOURCE_ORDER` preserved** — The core `get_permission_from_store_or_default()` loop stays identical. Same config-driven ordering. Same ability to skip/disable sources (e.g. removing 'group-regex' from the list). Same lazy lambda execution pattern. Zero performance regression.
- **Registry pattern** — Each resource type registers its 4 source callables (user, group, regex, group-regex) via a mapping. The generic function looks up the resource type in the registry and builds the sources config.

### Repository Base Class (REFAC-02)

- **Generic base class with type parameters** — `BasePermissionRepository[ModelT, EntityT]` provides get/list/create/update/delete. Subclasses only override when the resource needs special handling (e.g. scorer has 2-part key). Target ~50-60% code reduction across 28 repository classes.
- Type parameters are the SQLAlchemy model class and the entity dataclass.

### Feature Flag (WSFND-01)

- **`MLFLOW_ENABLE_WORKSPACES`** — Same name as upstream MLflow 3.10. Single flag controls workspace behavior for both upstream MLflow and the plugin. Simplest for operators.
- Disabled by default. Zero behavioral changes when off.
- Added to `AppConfig` class in `config.py`.

### Header Propagation (WSFND-02)

- **`X-MLFLOW-WORKSPACE` header** extracted in `AuthMiddleware`, added to ASGI scope `mlflow_oidc_auth` dict, flows through `AuthAwareWSGIMiddleware` to Flask `request.environ`.
- Only extracted/propagated when workspace feature flag is enabled.

### Database Migration (WSFND-03)

- **Both `workspace_permissions` AND `workspace_group_permissions` tables** created in Phase 1's Alembic migration. This pulls some Phase 3 schema work forward to have a single comprehensive migration.
- `workspace_permissions` composite PK: `(workspace, user_id, permission)`
- `workspace_group_permissions` composite PK: `(workspace, group_id, permission)`
- Foreign keys to existing `users` and `groups` tables.

### Default Workspace (WSFND-04)

- **Hardcoded `'default'`** — Matches upstream MLflow 3.10's `DEFAULT_WORKSPACE_NAME` constant. Not configurable. All existing resources implicitly belong to the default workspace.
- Migration seeds the default workspace.

### Default Workspace Access (WSFND-05)

- `grant_default_workspace_access` config option — when workspaces are first enabled, existing users get implicit access to the default workspace. Added to `AppConfig`.

### Bridge Extension (WSFND-06)

- **Typed `AuthContext` dataclass** — Replace individual environ keys (`mlflow_oidc_auth.username`, `mlflow_oidc_auth.is_admin`) with a typed context object: `AuthContext(username: str, is_admin: bool, workspace: str | None)`.
- Bridge exposes `get_request_workspace()` following existing patterns, but also exposes the full `AuthContext` object.
- Middleware sets the full `AuthContext` object in both ASGI scope and WSGI environ.
- All existing consumers (`get_fastapi_username()`, `get_fastapi_admin_status()`) continue to work — backed by the same `AuthContext` dataclass.

### Testing

- **Comprehensive tests** — Existing tests must pass unchanged after refactoring. Add new unit tests for:
  - Generic permission resolver with all 7 resource types
  - Repository base class CRUD operations
  - Feature flag enable/disable behavior
  - Bridge `get_request_workspace()` function
  - `AuthContext` dataclass and bridge integration
  - Migration (workspace tables created correctly, default workspace seeded)
- Use existing test patterns and conventions.

### Agent's Discretion

- Exact registry data structure (dict, TypedDict, or class) for the resource-type-to-store mapping
- Exact `BasePermissionRepository` method signatures — adapt to what works with SQLAlchemy generics
- Whether `AuthContext` lives in `bridge/` or gets its own module in `entities/` or `models/`
- Exact Alembic migration revision ID and naming convention
- How `grant_default_workspace_access` interacts with the migration vs. runtime (migration-time seed vs. app-startup check)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Permission Resolution
- `mlflow_oidc_auth/utils/permissions.py` — Current 8 `_permission_*_sources_config` functions and `get_permission_from_store_or_default()` core loop (466 lines)
- `mlflow_oidc_auth/permissions.py` — `get_permission()` function and Permission dataclass
- `mlflow_oidc_auth/models/__init__.py` — `PermissionResult` model

### Repository Pattern
- `mlflow_oidc_auth/repository/` — All 28 repository classes (see any for the CRUD pattern to generalize)
- `mlflow_oidc_auth/repository/experiment_permission.py` — Representative example of a permission repository
- `mlflow_oidc_auth/repository/scorer_permission.py` — Example with 2-part key (non-standard)
- `mlflow_oidc_auth/sqlalchemy_store.py` — Store facade that delegates to repositories

### Bridge Layer
- `mlflow_oidc_auth/bridge/user.py` — Current `get_fastapi_username()` and `get_fastapi_admin_status()` pattern
- `mlflow_oidc_auth/middleware/auth_middleware.py` — Where auth context is set in ASGI scope
- `mlflow_oidc_auth/middleware/auth_aware_wsgi_middleware.py` — ASGI-to-WSGI bridge that copies scope to environ

### Configuration
- `mlflow_oidc_auth/config.py` — `AppConfig` class, feature flags, config_manager integration
- `mlflow_oidc_auth/config_providers/manager.py` — Config provider chain

### Database Models & Migration
- `mlflow_oidc_auth/db/models/` — Existing ORM model patterns (one model per file, `Sql` prefix)
- `mlflow_oidc_auth/db/models/_base.py` — SQLAlchemy `DeclarativeBase`
- `mlflow_oidc_auth/db/migrations/` — Existing Alembic migration patterns
- `mlflow_oidc_auth/db/utils.py` — Migration execution on app startup

### Existing Tests
- `tests/` — Existing test patterns and conventions

### Research
- `.planning/research/ARCHITECTURE.md` — Target architecture diagrams and data flow
- `.planning/research/PITFALLS.md` — Pitfalls #1, #3, #5, #7, #10 directly affect this phase
- `.planning/research/SUMMARY.md` — Executive summary with critical findings

</canonical_refs>

<specifics>
## Specific Ideas

### Permission Registry Structure (from discussion)
The resource type registry should map each resource type to its 4 store method callables. Example structure:
```python
PERMISSION_REGISTRY = {
    "experiment": {
        "user": lambda eid, user: store.get_experiment_permission(eid, user).permission,
        "group": lambda eid, user: store.get_user_groups_experiment_permission(eid, user).permission,
        "regex": lambda eid, user: _get_experiment_permission_from_regex(...),
        "group-regex": lambda eid, user: _get_experiment_group_permission_from_regex(...),
    },
    # ... 6 more resource types
}
```

### AuthContext Bridge Pattern (from discussion)
```python
@dataclass
class AuthContext:
    username: str
    is_admin: bool
    workspace: str | None = None
```
Stored as a single object in scope/environ instead of individual keys. `get_fastapi_username()` and `get_fastapi_admin_status()` become thin wrappers that delegate to `get_auth_context().username` / `.is_admin`.

### Migration Tables (both in single migration)
```sql
CREATE TABLE workspace_permissions (
    workspace VARCHAR(255) NOT NULL,
    user_id INTEGER NOT NULL,
    permission VARCHAR(255) NOT NULL,
    PRIMARY KEY (workspace, user_id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE workspace_group_permissions (
    workspace VARCHAR(255) NOT NULL,
    group_id INTEGER NOT NULL,
    permission VARCHAR(255) NOT NULL,
    PRIMARY KEY (workspace, group_id),
    FOREIGN KEY (group_id) REFERENCES groups(id)
);
```

</specifics>

<deferred>
## Deferred Ideas

- Workspace permission CRUD store methods — Phase 2 (WSAUTH-02)
- Workspace permission resolution in the fallback chain — Phase 2 (WSAUTH-04)
- Workspace CRUD auth enforcement (before_request handlers) — Phase 2 (WSAUTH-01)
- Workspace management API (FastAPI router) — Phase 3 (WSMGMT-01, WSMGMT-02)
- OIDC workspace claim extraction — Phase 3 (WSOIDC-01)
- Workspace management UI — Phase 4 (WSMGMT-04, WSMGMT-05, WSMGMT-06)

</deferred>

---

*Phase: 01-refactoring-workspace-foundation*
*Context gathered: 2026-03-23 via discuss-phase*
