# Phase 1: Refactoring & Workspace Foundation - Research

**Researched:** 2026-03-23
**Domain:** Python/SQLAlchemy refactoring, Alembic migrations, FastAPI/Flask middleware bridge
**Confidence:** HIGH

## Summary

Phase 1 is a pure backend phase with two distinct halves: (1) refactoring permission resolution and repository classes to eliminate copy-paste duplication, and (2) laying workspace foundation plumbing (feature flag, DB migration, context propagation). No new external dependencies are introduced — all work uses the existing stack (SQLAlchemy 2.x, Alembic, FastAPI, Flask).

The refactoring half is well-bounded: `utils/permissions.py` (466 lines, 8 near-identical `_permission_*_sources_config` functions + 8 regex matching functions) collapses into a single registry-driven `resolve_permission()` function. The 29 repository files (28 classes + utils) share an identical CRUD pattern that maps to a generic `BasePermissionRepository[ModelT, EntityT]` base class. Both refactorings are mechanical — the patterns are already consistent, making extraction safe.

The workspace half is additive: new config flags, a new Alembic migration for two tables, and extending the existing bridge with a typed `AuthContext` dataclass. The critical constraint is that **all workspace behavior is gated behind `MLFLOW_ENABLE_WORKSPACES=false` by default**, ensuring zero behavioral changes for existing deployments.

**Primary recommendation:** Execute refactoring first (REFAC-01, REFAC-02), then workspace foundation (WSFND-01 through WSFND-06). The refactoring creates clean extension points that workspace code plugs into.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Permission Resolution (REFAC-01):** Single `resolve_permission(resource_type, resource_id, username)` with a registry/mapping of resource types to store methods. The 8 `_permission_*_sources_config` functions become data entries in a dict keyed by resource type. `PERMISSION_SOURCE_ORDER` preserved. Same lazy lambda execution pattern.
- **Repository Base Class (REFAC-02):** Generic `BasePermissionRepository[ModelT, EntityT]` provides get/list/create/update/delete. Subclasses only override when resource needs special handling (scorer 2-part key). Target ~50-60% code reduction.
- **Feature Flag (WSFND-01):** `MLFLOW_ENABLE_WORKSPACES` — same name as upstream MLflow 3.10. Disabled by default. Zero behavioral changes when off.
- **Header Propagation (WSFND-02):** `X-MLFLOW-WORKSPACE` header extracted in `AuthMiddleware`, flows through ASGI scope → WSGI environ. Only when flag enabled.
- **Database Migration (WSFND-03):** Both `workspace_permissions` AND `workspace_group_permissions` tables in single migration. Composite PKs: `(workspace, user_id, permission)` and `(workspace, group_id, permission)`. FKs to users/groups.
- **Default Workspace (WSFND-04):** Hardcoded `'default'` matching upstream MLflow 3.10. Not configurable. Migration seeds it.
- **Default Workspace Access (WSFND-05):** `grant_default_workspace_access` config option for existing user access.
- **Bridge Extension (WSFND-06):** Typed `AuthContext` dataclass replacing individual environ keys. `get_request_workspace()` following existing patterns. Existing functions become thin wrappers.

### Agent's Discretion
- Exact registry data structure (dict, TypedDict, or class) for resource-type-to-store mapping
- Exact `BasePermissionRepository` method signatures — adapt to SQLAlchemy generics
- Whether `AuthContext` lives in `bridge/` or gets its own module in `entities/` or `models/`
- Exact Alembic migration revision ID and naming convention
- How `grant_default_workspace_access` interacts with migration vs. runtime

### Deferred Ideas (OUT OF SCOPE)
- Workspace permission CRUD store methods — Phase 2 (WSAUTH-02)
- Workspace permission resolution in the fallback chain — Phase 2 (WSAUTH-04)
- Workspace CRUD auth enforcement (before_request handlers) — Phase 2 (WSAUTH-01)
- Workspace management API (FastAPI router) — Phase 3 (WSMGMT-01, WSMGMT-02)
- OIDC workspace claim extraction — Phase 3 (WSOIDC-01)
- Workspace management UI — Phase 4 (WSMGMT-04, WSMGMT-05, WSMGMT-06)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REFAC-01 | Permission resolution refactored into generic `resolve_permission()` function to eliminate 8 copy-paste functions in `utils/permissions.py` | Registry pattern analysis, all 8 source config functions mapped, regex function deduplication identified, consumer inventory complete |
| REFAC-02 | Repository base class for permissions to reduce duplication across 28+ repository classes | All 29 repo files analyzed, 4 repo categories identified (user/group/regex/group-regex), special cases documented (scorer 2-part key, gateway rename/wipe) |
| WSFND-01 | Feature flag `MLFLOW_ENABLE_WORKSPACES` gates all workspace behavior | AppConfig pattern documented, `config_manager.get_bool()` usage verified, existing feature flag pattern (`OIDC_GEN_AI_GATEWAY_ENABLED`) identified as template |
| WSFND-02 | `X-MLFLOW-WORKSPACE` header propagated through middleware bridge | Full data flow mapped: AuthMiddleware → ASGI scope dict → AuthInjectingWSGIApp → Flask environ → bridge functions |
| WSFND-03 | Alembic migration adds workspace tables with composite PKs | Current migration HEAD identified (`6a7b8c9def01`), migration pattern documented, env.py autogenerate setup verified |
| WSFND-04 | Default workspace seeded on migration | Existing migration patterns analyzed, `op.execute(INSERT)` pattern for seed data identified |
| WSFND-05 | `grant_default_workspace_access` config option | AppConfig extension pattern documented, runtime vs. migration-time seeding analyzed |
| WSFND-06 | Bridge extension with `get_request_workspace()` and typed `AuthContext` | Current bridge code (58 lines) fully analyzed, environ key patterns mapped, middleware injection points identified |
</phase_requirements>

## Standard Stack

### Core (already in project — no new dependencies)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLAlchemy | >=2.0.46, <3 | ORM, `Mapped[T]` type annotations, generic repository types | Already used throughout, `DeclarativeBase` in `_base.py` |
| Alembic | <2, !=1.18.4 | Database migration for workspace tables | Already manages all auth DB schema |
| FastAPI | >=0.132.0 | Middleware extension for workspace header | Already the primary ASGI framework |
| Flask | <4 | WSGI environ bridge target | Already mounted via `AuthAwareWSGIMiddleware` |
| Python dataclasses | stdlib | `AuthContext` dataclass | Already used for `Permission`, entity base classes |

### Supporting (already in project)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `asgiref` | >=3.11.1 | `WsgiToAsgi` adapter in middleware | Already used in `auth_aware_wsgi_middleware.py` |
| `python-dotenv` | <2 | `.env` loading for new config vars | Already loaded in `config.py` |
| `typing` | stdlib | `Generic[T]`, `TypeVar`, `Dict`, `Callable` | For generic base class type parameters |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `dataclass` for AuthContext | Pydantic `BaseModel` | Pydantic adds validation but AuthContext is internal — dataclass is simpler, consistent with `Permission` dataclass pattern |
| Dict registry for permission types | Enum-based registry class | Enum is more type-safe but dict matches existing `PERMISSION_SOURCES_CONFIG` pattern exactly |
| Abstract base class for repos | Protocol (structural subtyping) | Protocol avoids inheritance but repos already use `self._Session` initialization pattern — ABC is clearer |

## Architecture Patterns

### Permission Resolution Registry (REFAC-01)

**What:** Replace 8 `_permission_*_sources_config()` functions with a single registry mapping resource types to their 4 store method callables.

**Current pattern (duplicated 8×):**
```python
def _permission_experiment_sources_config(experiment_id: str, username: str) -> Dict[str, Callable[[], str]]:
    return {
        "user": lambda ...: store.get_experiment_permission(eid, user).permission,
        "group": lambda ...: store.get_user_groups_experiment_permission(eid, user).permission,
        "regex": lambda ...: _get_experiment_permission_from_regex(...),
        "group-regex": lambda ...: _get_experiment_group_permission_from_regex(...),
    }
```

**Target pattern (one registry, one function):**
```python
# Registry maps resource_type → config factory
PERMISSION_REGISTRY: Dict[str, Callable[..., Dict[str, Callable[[], str]]]] = {
    "experiment": _build_experiment_sources,
    "registered_model": _build_registered_model_sources,
    "prompt": _build_prompt_sources,
    "scorer": _build_scorer_sources,
    "gateway_endpoint": _build_gateway_endpoint_sources,
    "gateway_secret": _build_gateway_secret_sources,
    "gateway_model_definition": _build_gateway_model_definition_sources,
}

def resolve_permission(resource_type: str, resource_id: str, username: str, **kwargs) -> PermissionResult:
    """Single entry point for all permission resolution."""
    builder = PERMISSION_REGISTRY[resource_type]
    sources_config = builder(resource_id, username, **kwargs)
    return get_permission_from_store_or_default(sources_config)
```

**Key design decisions:**
- `get_permission_from_store_or_default()` (lines 422-466) stays UNCHANGED — it's the core loop that iterates `PERMISSION_SOURCE_ORDER`
- Each registry entry is a thin builder function (replaces the 8 `_permission_*_sources_config` functions)
- `**kwargs` handles scorer's extra `scorer_name` parameter without polluting the base signature
- Regex matching functions can be deduplicated: 6 of 8 are identical (match name against regex list), only experiment needs `_get_tracking_store().get_experiment(id).name` lookup

**Regex function deduplication:**
```python
def _match_regex_permission(regexes: List, name: str, label: str) -> str:
    """Generic regex matcher for any resource type."""
    for regex in regexes:
        if re.match(regex.regex, name):
            logger.debug(f"Regex permission found for {label} {name}: {regex.permission}")
            return regex.permission
    raise MlflowException(f"{label} {name}", error_code=RESOURCE_DOES_NOT_EXIST)
```
Only experiment needs a wrapper that resolves `experiment_id → experiment_name` before calling this.

**Consumer impact:** The public API functions (`effective_experiment_permission`, `can_read_experiment`, etc.) become thin wrappers around `resolve_permission()`. All 876+ call sites across the codebase continue working unchanged.

### Generic Repository Base Class (REFAC-02)

**What:** Extract common CRUD operations into `BasePermissionRepository[ModelT, EntityT]`.

**Current pattern (duplicated 28×):**
```python
class ExperimentPermissionRepository:
    def __init__(self, session_maker):
        self._Session: Callable[[], Session] = session_maker

    def _get_experiment_permission(self, session, experiment_id, username):
        # query + join SqlUser + filter + .one()
        ...

    def grant_permission(self, experiment_id, username, permission):
        _validate_permission(permission)
        with self._Session() as session:
            user = get_user(session, username)
            perm = SqlExperimentPermission(...)
            session.add(perm); session.flush()
            return perm.to_mlflow_entity()
    # + get_permission, list_*, update_permission, revoke_permission
```

**Target pattern:**
```python
from typing import Generic, TypeVar, Type

ModelT = TypeVar("ModelT")   # SQLAlchemy model
EntityT = TypeVar("EntityT") # Entity dataclass

class BasePermissionRepository(Generic[ModelT, EntityT]):
    model_class: Type[ModelT]    # Set by subclass
    resource_id_column: str      # e.g., "experiment_id"

    def __init__(self, session_maker: Callable[[], Session]):
        self._Session = session_maker

    def _get_permission(self, session: Session, resource_id: str, username: str) -> ModelT:
        # Generic query using self.model_class and self.resource_id_column
        ...

    def grant_permission(self, resource_id: str, username: str, permission: str) -> EntityT:
        # Generic create using self.model_class
        ...

    def get_permission(self, resource_id: str, username: str) -> EntityT:
        ...

    def list_permissions_for_user(self, username: str) -> List[EntityT]:
        ...

    def update_permission(self, resource_id: str, username: str, permission: str) -> EntityT:
        ...

    def revoke_permission(self, resource_id: str, username: str) -> None:
        ...

class ExperimentPermissionRepository(BasePermissionRepository[SqlExperimentPermission, ExperimentPermission]):
    model_class = SqlExperimentPermission
    resource_id_column = "experiment_id"
    # No method overrides needed — fully generic
```

**Repository categories and handling:**

| Category | Count | Base Class Fit | Special Handling |
|----------|-------|----------------|------------------|
| User permission repos | 7 | Direct — standard (resource_id, username) key | None |
| Group permission repos | 7 | Direct — standard (resource_id, group_name) key | group lookup instead of user lookup |
| User regex repos | 7 | Separate base — different columns (regex, priority, user_id) | Different CRUD shape |
| Group regex repos | 7 | Separate base — different columns (regex, priority, group_id) | Different CRUD shape |

**Special cases requiring override:**
1. **Scorer** — 2-part key: `(experiment_id, scorer_name)` instead of single `resource_id`. Override `_get_permission()`, `grant_permission()`, etc.
2. **Gateway endpoint/secret/model-definition** — Extra `rename()` and `wipe()` methods. Add these to a `RenameablePermissionRepository` mixin or just define them in subclasses.
3. **Prompt** — Currently uses `registered_model_permission` store methods (reuses model permission logic). This is a known inconsistency that should be preserved during refactoring, not fixed.

**Recommended base classes:**
- `BaseUserPermissionRepository[ModelT, EntityT]` — for user permission repos (7 classes)
- `BaseGroupPermissionRepository[ModelT, EntityT]` — for group permission repos (7 classes)
- `BaseRegexPermissionRepository[ModelT, EntityT]` — for user regex repos (7 classes)
- `BaseGroupRegexPermissionRepository[ModelT, EntityT]` — for group regex repos (7 classes)

Alternatively, a single base with a `lookup_column` parameter (`user_id` vs `group_id`) could serve both user and group repos, reducing to 2 base classes.

### AuthContext Bridge Pattern (WSFND-02, WSFND-06)

**What:** Replace individual environ keys with a typed `AuthContext` dataclass.

**Current flow (3 individual keys):**
```
AuthMiddleware.dispatch() → request.scope["mlflow_oidc_auth"] = {"username": ..., "is_admin": ...}
                          ↓
AuthInjectingWSGIApp.__call__() → environ["mlflow_oidc_auth.username"] = username
                                   environ["mlflow_oidc_auth.is_admin"] = is_admin
                          ↓
bridge/user.py → request.environ.get("mlflow_oidc_auth.username")
                 request.environ.get("mlflow_oidc_auth.is_admin", False)
```

**Target flow (single AuthContext object):**
```
AuthMiddleware.dispatch() → request.scope["mlflow_oidc_auth"] = AuthContext(username=..., is_admin=..., workspace=...)
                          ↓
AuthInjectingWSGIApp.__call__() → environ["mlflow_oidc_auth"] = auth_context  # single key
                          ↓
bridge/user.py → get_auth_context() → request.environ["mlflow_oidc_auth"]
                 get_fastapi_username() → get_auth_context().username  # backward compat wrapper
                 get_fastapi_admin_status() → get_auth_context().is_admin  # backward compat wrapper
                 get_request_workspace() → get_auth_context().workspace  # new
```

**AuthContext dataclass:**
```python
from dataclasses import dataclass

@dataclass(frozen=True)
class AuthContext:
    username: str
    is_admin: bool
    workspace: str | None = None
```

**Placement recommendation:** `mlflow_oidc_auth/entities/auth_context.py` — it's a pure data class (no dependencies), consistent with other entities in `entities/`. Re-exported from `entities/__init__.py`.

**Workspace header extraction (only when flag enabled):**
```python
# In AuthMiddleware.dispatch():
workspace = None
if config.MLFLOW_ENABLE_WORKSPACES:
    workspace = request.headers.get("x-mlflow-workspace")

request.scope["mlflow_oidc_auth"] = AuthContext(
    username=username,
    is_admin=request.state.is_admin,
    workspace=workspace,
)
```

### Feature Flag Pattern (WSFND-01)

**What:** Add `MLFLOW_ENABLE_WORKSPACES` to `AppConfig`.

**Pattern (matches existing `OIDC_GEN_AI_GATEWAY_ENABLED`):**
```python
# In AppConfig.__init__():
self.MLFLOW_ENABLE_WORKSPACES = config_manager.get_bool("MLFLOW_ENABLE_WORKSPACES", default=False)
self.GRANT_DEFAULT_WORKSPACE_ACCESS = config_manager.get_bool("GRANT_DEFAULT_WORKSPACE_ACCESS", default=True)
```

**Usage pattern throughout code:**
```python
from mlflow_oidc_auth.config import config

if config.MLFLOW_ENABLE_WORKSPACES:
    # workspace-aware behavior
else:
    # existing behavior unchanged
```

### Database Migration Pattern (WSFND-03, WSFND-04)

**What:** Single Alembic migration creating `workspace_permissions` and `workspace_group_permissions` tables, seeding default workspace.

**Migration pattern (following existing `6a7b8c9def01`):**
```python
"""add_workspace_permissions

Revision ID: <generated>
Revises: 6a7b8c9def01
"""

from alembic import op
import sqlalchemy as sa

revision = "<generated>"
down_revision = "6a7b8c9def01"

def upgrade() -> None:
    op.create_table(
        "workspace_permissions",
        sa.Column("workspace", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("permission", sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_workspace_perm_user_id"),
        sa.PrimaryKeyConstraint("workspace", "user_id", name="pk_workspace_permissions"),
    )

    op.create_table(
        "workspace_group_permissions",
        sa.Column("workspace", sa.String(length=255), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("permission", sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], name="fk_workspace_group_perm_group_id"),
        sa.PrimaryKeyConstraint("workspace", "group_id", name="pk_workspace_group_permissions"),
    )

def downgrade() -> None:
    op.drop_table("workspace_group_permissions")
    op.drop_table("workspace_permissions")
```

**Default workspace seeding:** Do NOT seed in migration — seed at app startup in `create_app()` when `MLFLOW_ENABLE_WORKSPACES` is enabled and `GRANT_DEFAULT_WORKSPACE_ACCESS` is true. Rationale: migrations run even when workspaces are disabled; the tables should exist (schema readiness) but data should only be populated when the feature is active.

**ORM models needed (but NOT store methods — those are Phase 2):**
```python
# db/models/workspace.py
class SqlWorkspacePermission(Base):
    __tablename__ = "workspace_permissions"
    workspace: Mapped[str] = mapped_column(String(255), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    permission: Mapped[str] = mapped_column(String(255), nullable=False)

class SqlWorkspaceGroupPermission(Base):
    __tablename__ = "workspace_group_permissions"
    workspace: Mapped[str] = mapped_column(String(255), primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), primary_key=True)
    permission: Mapped[str] = mapped_column(String(255), nullable=False)
```

### Recommended Project Structure for New/Modified Files

```
mlflow_oidc_auth/
├── entities/
│   ├── auth_context.py          # NEW: AuthContext dataclass
│   └── __init__.py              # MODIFIED: re-export AuthContext
├── utils/
│   └── permissions.py           # MODIFIED: registry + resolve_permission()
├── repository/
│   ├── _base.py                 # NEW: BasePermissionRepository generic classes
│   ├── experiment_permission.py # MODIFIED: extends base class
│   └── ... (all repos)          # MODIFIED: extend base classes
├── bridge/
│   └── user.py                  # MODIFIED: AuthContext-based, add get_request_workspace()
├── middleware/
│   ├── auth_middleware.py        # MODIFIED: AuthContext in scope, workspace header
│   └── auth_aware_wsgi_middleware.py  # MODIFIED: pass AuthContext object
├── config.py                    # MODIFIED: add MLFLOW_ENABLE_WORKSPACES, GRANT_DEFAULT_WORKSPACE_ACCESS
├── db/
│   ├── models/
│   │   ├── workspace.py         # NEW: SqlWorkspacePermission, SqlWorkspaceGroupPermission
│   │   └── __init__.py          # MODIFIED: re-export new models
│   └── migrations/
│       └── versions/
│           └── <rev>_add_workspace_permissions.py  # NEW: migration
└── app.py                       # MODIFIED: default workspace seeding logic on startup
```

### Anti-Patterns to Avoid
- **Don't add `workspace` parameter to existing permission functions** — the workspace foundation is plumbing only; permission resolution doesn't use workspace yet (Phase 2: WSAUTH-04)
- **Don't create workspace CRUD store methods** — explicitly deferred to Phase 2 (WSAUTH-02)
- **Don't modify `before_request.py` or `after_request.py`** — workspace enforcement is Phase 2 (WSAUTH-01)
- **Don't modify any frontend code** — workspace UI is Phase 4
- **Don't make `get_permission_from_store_or_default()` workspace-aware** — the core loop stays unchanged; workspace fallback is Phase 2

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Generic repository pattern | Custom metaclass or decorator-based code generation | Python `typing.Generic` + `TypeVar` with class attributes | SQLAlchemy 2.x works well with generic type parameters; simpler to debug |
| ASGI-to-WSGI context passing | Custom WSGI wrapper with manual scope copying | Existing `AuthInjectingWSGIApp` pattern (just extend it) | Pattern is proven, has tests, handles edge cases |
| Config boolean parsing | Manual string-to-bool conversion | `config_manager.get_bool()` | Already handles "true"/"false"/"1"/"0" parsing consistently |
| Migration revision IDs | Manual hex string | `alembic revision --autogenerate` or let Alembic generate | Avoid collisions with other branches |

## Common Pitfalls

### Pitfall 1: Breaking Existing Test Mocks After Refactoring
**What goes wrong:** Existing tests mock specific functions like `store.get_experiment_permission()` or patch `_permission_experiment_sources_config`. After refactoring to a registry, these mock targets move and tests silently pass with incorrect behavior or fail with import errors.
**Why it happens:** Tests use string-based patching (`@patch("mlflow_oidc_auth.utils.permissions._permission_experiment_sources_config")`) which breaks when the function is renamed or moved.
**How to avoid:** Run full test suite (`tox -e py312`) after EACH refactoring step, not just at the end. Keep backward-compatible function names as thin wrappers during the transition.
**Warning signs:** Tests pass locally but coverage drops; mock targets in test files reference functions that no longer exist.

### Pitfall 2: Scorer 2-Part Key Breaking Generic Base Class
**What goes wrong:** The generic base class assumes a single `resource_id` parameter. Scorer needs `(experiment_id, scorer_name)`. Trying to force this into a single-key abstraction leads to awkward tuple-packing or breaks the type signatures.
**Why it happens:** Scorer is the only resource type with a composite natural key (experiment_id + scorer_name). All other resources use a single string identifier.
**How to avoid:** Design the base class to accept **kwargs for the resource identifier. Scorer subclass overrides `_get_permission()`, `grant_permission()`, `update_permission()`, and `revoke_permission()` with its 2-part key signature. Alternatively, accept that scorer doesn't reduce as much as the other 6 types.
**Warning signs:** Base class has complex conditional logic for "is this a scorer?" — that defeats the purpose of the base class.

### Pitfall 3: AuthContext Breaking Serialization in WSGI Environ
**What goes wrong:** WSGI environ values are typically strings. Storing a dataclass object in `environ["mlflow_oidc_auth"]` works because `asgiref.wsgi.WsgiToAsgi` preserves Python objects — but only if the environ key doesn't collide with WSGI reserved keys and the object is picklable.
**Why it happens:** The WSGI spec says environ values should be native strings, but the implementation (asgiref) passes Python objects through.
**How to avoid:** The current code already stores non-string values (`is_admin` is a boolean) in environ, so this pattern is proven. Just ensure `AuthContext` is a simple dataclass with no unpicklable references. Using `frozen=True` ensures immutability.
**Warning signs:** `AuthContext` object arrives as `None` or raises `AttributeError` in Flask bridge.

### Pitfall 4: Migration Running When Feature Is Disabled
**What goes wrong:** Alembic migration runs on app startup (`migrate_if_needed()`), creating workspace tables even when `MLFLOW_ENABLE_WORKSPACES=false`. This is actually CORRECT behavior — schema should always be current. But developers might accidentally add data seeding in the migration that shouldn't run when disabled.
**Why it happens:** Conflating schema migration (always run) with data initialization (conditional on feature flag).
**How to avoid:** Keep migration purely structural (CREATE TABLE only). Move all data seeding (default workspace access grants) to app startup code gated by the feature flag.
**Warning signs:** Users with `MLFLOW_ENABLE_WORKSPACES=false` see unexpected data in workspace tables.

### Pitfall 5: Prompt Permission Reusing Registered Model Store Methods
**What goes wrong:** The existing `_permission_prompt_sources_config` calls `store.get_registered_model_permission()` for its "user" and "group" sources (lines 33-34 of permissions.py). This is NOT a bug — prompts use the same permission model as registered models. But when building the registry, this mapping must be preserved, not "fixed."
**Why it happens:** Prompts were added after registered models and share the same permission structure. The store methods are intentionally shared.
**How to avoid:** The registry entry for "prompt" must map to the same store methods as "registered_model" for user/group sources, but different store methods for regex/group-regex (prompt-specific regex tables exist).
**Warning signs:** Prompt permission checks break after refactoring because someone "corrected" the store method to a non-existent `store.get_prompt_permission()`.

### Pitfall 6: Consumer Functions Breaking Public API
**What goes wrong:** Functions like `effective_experiment_permission()`, `can_read_experiment()`, `can_manage_registered_model()` are used extensively (876+ grep matches). If these are removed or their signatures change, every consumer breaks.
**Why it happens:** Enthusiasm for "clean" refactoring removes the old API surface.
**How to avoid:** Keep ALL existing public functions as thin wrappers. They call `resolve_permission()` internally but present the same signature externally. No consumer needs to change.
**Warning signs:** Grep for removed function names in hooks/, validators/, routers/ after refactoring.

## Code Examples

### Permission Registry Definition
```python
# mlflow_oidc_auth/utils/permissions.py

from typing import Callable, Dict

# Resource type constants
EXPERIMENT = "experiment"
REGISTERED_MODEL = "registered_model"
PROMPT = "prompt"
SCORER = "scorer"
GATEWAY_ENDPOINT = "gateway_endpoint"
GATEWAY_SECRET = "gateway_secret"
GATEWAY_MODEL_DEFINITION = "gateway_model_definition"

def _build_experiment_sources(experiment_id: str, username: str) -> Dict[str, Callable[[], str]]:
    return {
        "user": lambda: store.get_experiment_permission(experiment_id, username).permission,
        "group": lambda: store.get_user_groups_experiment_permission(experiment_id, username).permission,
        "regex": lambda: _match_regex_permission(
            store.list_experiment_regex_permissions(username),
            _get_tracking_store().get_experiment(experiment_id).name,
            "experiment",
        ),
        "group-regex": lambda: _match_regex_permission(
            store.list_group_experiment_regex_permissions_for_groups_ids(
                store.get_groups_ids_for_user(username)
            ),
            _get_tracking_store().get_experiment(experiment_id).name,
            "experiment",
        ),
    }

# Registry
PERMISSION_REGISTRY: Dict[str, Callable[..., Dict[str, Callable[[], str]]]] = {
    EXPERIMENT: _build_experiment_sources,
    REGISTERED_MODEL: _build_registered_model_sources,
    PROMPT: _build_prompt_sources,
    SCORER: _build_scorer_sources,
    GATEWAY_ENDPOINT: _build_gateway_endpoint_sources,
    GATEWAY_SECRET: _build_gateway_secret_sources,
    GATEWAY_MODEL_DEFINITION: _build_gateway_model_definition_sources,
}

def resolve_permission(resource_type: str, resource_id: str, username: str, **kwargs) -> PermissionResult:
    """Resolve effective permission for any resource type."""
    builder = PERMISSION_REGISTRY[resource_type]
    sources_config = builder(resource_id, username, **kwargs)
    return get_permission_from_store_or_default(sources_config)

# Backward-compatible wrappers (unchanged signatures)
def effective_experiment_permission(experiment_id: str, user: str) -> PermissionResult:
    return resolve_permission(EXPERIMENT, experiment_id, user)

def can_read_experiment(experiment_id: str, user: str) -> bool:
    return resolve_permission(EXPERIMENT, experiment_id, user).permission.can_read
```

### Generic Repository Base Class
```python
# mlflow_oidc_auth/repository/_base.py

from typing import Callable, Generic, List, Type, TypeVar
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, MultipleResultsFound, NoResultFound
from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import INVALID_STATE, RESOURCE_ALREADY_EXISTS, RESOURCE_DOES_NOT_EXIST
from mlflow_oidc_auth.db.models import SqlUser
from mlflow_oidc_auth.permissions import _validate_permission
from mlflow_oidc_auth.repository.utils import get_user

ModelT = TypeVar("ModelT")
EntityT = TypeVar("EntityT")

class BaseUserPermissionRepository(Generic[ModelT, EntityT]):
    """Base class for user-level permission repositories."""
    model_class: Type[ModelT]
    resource_id_attr: str  # attribute name on the model, e.g., "experiment_id"

    def __init__(self, session_maker: Callable[[], Session]):
        self._Session = session_maker

    def _get_resource_id_filter(self, resource_id: str):
        return getattr(self.model_class, self.resource_id_attr) == resource_id

    def _get_permission(self, session: Session, resource_id: str, username: str) -> ModelT:
        try:
            return (
                session.query(self.model_class)
                .join(SqlUser, self.model_class.user_id == SqlUser.id)
                .filter(self._get_resource_id_filter(resource_id), SqlUser.username == username)
                .one()
            )
        except NoResultFound:
            raise MlflowException(
                f"No permission for {self.resource_id_attr}={resource_id}, user={username}",
                RESOURCE_DOES_NOT_EXIST,
            )
        except MultipleResultsFound:
            raise MlflowException(
                f"Multiple perms for {self.resource_id_attr}={resource_id}, user={username}",
                INVALID_STATE,
            )

    def grant_permission(self, resource_id: str, username: str, permission: str) -> EntityT:
        _validate_permission(permission)
        with self._Session() as session:
            try:
                user = get_user(session, username)
                perm = self.model_class(**{self.resource_id_attr: resource_id, "user_id": user.id, "permission": permission})
                session.add(perm)
                session.flush()
                return perm.to_mlflow_entity()
            except IntegrityError as e:
                raise MlflowException(
                    f"Permission already exists ({resource_id}, {username}): {e}",
                    RESOURCE_ALREADY_EXISTS,
                )

    # ... get_permission, list_*, update_permission, revoke_permission follow same pattern
```

### AuthContext and Bridge Extension
```python
# mlflow_oidc_auth/entities/auth_context.py
from dataclasses import dataclass

@dataclass(frozen=True)
class AuthContext:
    username: str
    is_admin: bool
    workspace: str | None = None

# mlflow_oidc_auth/bridge/user.py (modified)
from mlflow_oidc_auth.entities.auth_context import AuthContext
from mlflow_oidc_auth.logger import get_logger

logger = get_logger()

def get_auth_context() -> AuthContext:
    """Get full auth context from Flask request environ."""
    from flask import request
    ctx = request.environ.get("mlflow_oidc_auth")
    if isinstance(ctx, AuthContext):
        return ctx
    raise Exception("Could not retrieve auth context")

def get_fastapi_username() -> str:
    """Backward-compatible wrapper."""
    return get_auth_context().username

def get_fastapi_admin_status() -> bool:
    """Backward-compatible wrapper."""
    try:
        return get_auth_context().is_admin
    except Exception:
        return False

def get_request_workspace() -> str | None:
    """Get workspace from auth context. Returns None if workspaces disabled."""
    try:
        return get_auth_context().workspace
    except Exception:
        return None
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Individual WSGI environ keys | Typed context object in environ | This phase | Single source of truth, extensible without touching middleware for each new field |
| Copy-paste permission functions per resource type | Registry-driven generic resolution | This phase | New resource types added with ~5 lines (registry entry) instead of ~60 lines |
| Copy-paste repository classes | Generic base class with type parameters | This phase | ~50-60% code reduction, consistent behavior across all resource types |

## Open Questions

1. **`_build_scorer_sources` signature**
   - What we know: Scorer needs `experiment_id` AND `scorer_name`. All other builders need only `resource_id` and `username`.
   - What's unclear: Should `resolve_permission()` accept `**kwargs` and pass them through, or should scorer have its own top-level function?
   - Recommendation: Use `**kwargs` — `resolve_permission("scorer", experiment_id, username, scorer_name=scorer_name)`. The builder extracts `kwargs["scorer_name"]`. Clean, explicit, type-checkable with overloads if desired.

2. **Prompt-registered_model store method sharing**
   - What we know: `_permission_prompt_sources_config` calls `store.get_registered_model_permission()` for user/group sources.
   - What's unclear: Is this intentional or a bug? No separate `store.get_prompt_permission()` exists for user-level.
   - Recommendation: Preserve as-is. The registry entry for "prompt" explicitly maps to registered model store methods. Document with a comment. Phase 2+ can address if needed.

3. **`grant_default_workspace_access` — migration-time vs. runtime**
   - What we know: Migration creates tables. Config flag controls whether to grant access.
   - What's unclear: Should existing users get workspace_permissions rows on first startup, or should it be a lazy check at permission resolution time?
   - Recommendation: App startup in `create_app()` — when `MLFLOW_ENABLE_WORKSPACES=true` and `GRANT_DEFAULT_WORKSPACE_ACCESS=true`, insert rows for all existing users. This is explicit and auditable. Lazy checks add complexity to the permission resolution hot path.

4. **Number of base classes for repositories**
   - What we know: 4 categories of repos (user/group/regex/group-regex).
   - What's unclear: Should there be 4 separate base classes or 2 (permission + regex) with a parameter for user vs. group?
   - Recommendation: Start with 2 base classes — `BaseUserPermissionRepository` and `BaseRegexPermissionRepository`. Group variants extend these with a `_get_group` instead of `_get_user` lookup. This maximizes code sharing while keeping the inheritance hierarchy shallow.

## Sources

### Primary (HIGH confidence)
- Direct codebase analysis: `utils/permissions.py` (466 lines — all 8 source config functions, all 8 regex functions, core loop)
- Direct codebase analysis: `repository/` (29 files — all CRUD patterns, special cases)
- Direct codebase analysis: `bridge/user.py` (58 lines — full bridge pattern)
- Direct codebase analysis: `middleware/auth_middleware.py` (235 lines — scope injection at line 221)
- Direct codebase analysis: `middleware/auth_aware_wsgi_middleware.py` (85 lines — environ injection at lines 41-42)
- Direct codebase analysis: `config.py` (110 lines — feature flag pattern at line 98)
- Direct codebase analysis: `db/models/experiment.py` (75 lines — ORM model pattern)
- Direct codebase analysis: `db/models/_base.py` (5 lines — DeclarativeBase)
- Direct codebase analysis: `db/migrations/versions/6a7b8c9def01_add_gateway_permissions.py` (165 lines — migration pattern)
- Direct codebase analysis: `db/migrations/env.py` (82 lines — autogenerate, version_table)
- Direct codebase analysis: `db/utils.py` (37 lines — migrate_if_needed on startup)
- Direct codebase analysis: `entities/_base.py` (69 lines — PermissionBase, RegexPermissionBase)
- Direct codebase analysis: `repository/scorer_permission.py` (84 lines — 2-part key pattern)
- Direct codebase analysis: `repository/gateway_endpoint_permissions.py` (98 lines — rename/wipe pattern)
- Direct codebase analysis: `permissions.py` (102 lines — Permission dataclass, get_permission)
- Direct codebase analysis: `store.py` (5 lines — singleton pattern)

### Secondary (MEDIUM confidence)
- `.planning/research/PITFALLS.md` — pitfalls #1, #3, #5, #7, #10 inform this phase's design constraints
- `.planning/REQUIREMENTS.md` — all 8 phase requirements verified against codebase
- `.planning/phases/01-refactoring-workspace-foundation/01-CONTEXT.md` — locked decisions from user discussion

### Tertiary (LOW confidence)
- None — all findings based on direct codebase analysis

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies, all existing libraries verified in codebase
- Architecture patterns: HIGH — patterns directly extracted from existing code with minimal abstraction
- Pitfalls: HIGH — pitfalls identified from direct code analysis, confirmed by project PITFALLS.md research
- Migration: HIGH — exact migration pattern, revision chain, and env.py configuration verified

**Research date:** 2026-03-23
**Valid until:** 2026-04-22 (30 days — stable domain, no external dependency changes expected)

---
*Phase: 01-refactoring-workspace-foundation*
*Research completed: 2026-03-23*
