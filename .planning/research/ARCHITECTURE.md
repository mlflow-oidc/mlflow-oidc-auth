# Architecture Research

**Domain:** Workspace CRUD management, scoped search filtering, regex workspace permissions, and global workspace picker for mlflow-oidc-auth v1.1
**Researched:** 2026-03-24
**Confidence:** HIGH

## System Overview

### Current State (Post-v1.0)

```
┌─────────────────────────────────────────────────────────────────────┐
│                     ASGI Entry (Uvicorn)                            │
├─────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │ ProxyHeaders │→ │AuthMiddleware│→ │  FastAPI Router Layer     │  │
│  │  Middleware   │  │(Basic/Bearer │  │ (15 routers incl.        │  │
│  │              │  │ /Session)    │  │  workspace_permissions)  │  │
│  │              │  │ Sets:        │  │                          │  │
│  │              │  │ AuthContext(  │  │ No workspace CRUD proxy  │  │
│  │              │  │  username,   │  │ No regex workspace perms │  │
│  │              │  │  is_admin,   │  │                          │  │
│  │              │  │  workspace)  │  │                          │  │
│  └──────────────┘  └──────┬───────┘  └──────────────────────────┘  │
│                           │                                         │
├───────────────────────────┼─────────────────────────────────────────┤
│               AuthAwareWSGIMiddleware                               │
│          Copies AuthContext → WSGI environ                          │
├───────────────────────────┼─────────────────────────────────────────┤
│                     Flask (MLflow App)                               │
│  ┌───────────────┐  ┌──────────────┐  ┌─────────────────────────┐  │
│  │ before_request│→ │ MLflow Core  │→ │    after_request         │  │
│  │ (workspace    │  │ (handles     │  │ (_filter_list_workspaces │  │
│  │  CRUD valida- │  │  workspace   │  │  but NO experiment/     │  │
│  │  tors: admin  │  │  RPCs nati-  │  │  model workspace-scope  │  │
│  │  only CUD)    │  │  vely)       │  │  filtering)             │  │
│  └───────────────┘  └──────────────┘  └─────────────────────────┘  │
├─────────────────────────────────────────────────────────────────────┤
│  Permission Resolution: resource → workspace fallback → default     │
│  Workspace cache: TTLCache (user + group, no regex)                 │
├─────────────────────────────────────────────────────────────────────┤
│  SqlAlchemyStore → Repos (standalone workspace repos, no regex)     │
│  DB: workspace_permissions, workspace_group_permissions             │
└─────────────────────────────────────────────────────────────────────┘
```

### Target State (v1.1)

```
┌─────────────────────────────────────────────────────────────────────┐
│                     ASGI Entry (Uvicorn)                            │
├─────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │ ProxyHeaders │→ │AuthMiddleware│→ │  FastAPI Router Layer     │  │
│  │  Middleware   │  │ (unchanged)  │  │ + NEW: workspace_router  │  │
│  │              │  │              │  │   (CRUD proxy to MLflow) │  │
│  │              │  │              │  │ + NEW: ws regex perm     │  │
│  │              │  │              │  │   endpoints on existing  │  │
│  │              │  │              │  │   workspace_permissions  │  │
│  └──────────────┘  └──────┬───────┘  └──────────────────────────┘  │
│                           │                                         │
├───────────────────────────┼─────────────────────────────────────────┤
│               AuthAwareWSGIMiddleware (unchanged)                    │
├───────────────────────────┼─────────────────────────────────────────┤
│                     Flask (MLflow App)                               │
│  ┌───────────────┐  ┌──────────────┐  ┌─────────────────────────┐  │
│  │ before_request│→ │ MLflow Core  │→ │    after_request         │  │
│  │ MODIFIED:     │  │ (unchanged)  │  │ MODIFIED:                │  │
│  │ update/delete │  │              │  │ _filter_search_*         │  │
│  │ workspace now │  │              │  │ now also checks          │  │
│  │ allows MANAGE │  │              │  │ workspace membership     │  │
│  │ (not admin    │  │              │  │                          │  │
│  │  only)        │  │              │  │                          │  │
│  └───────────────┘  └──────────────┘  └─────────────────────────┘  │
├─────────────────────────────────────────────────────────────────────┤
│  Permission Resolution: resource → workspace fallback → default     │
│  Workspace cache: MODIFIED — adds regex + group-regex lookup        │
├─────────────────────────────────────────────────────────────────────┤
│  SqlAlchemyStore → Repos                                            │
│  + NEW: WorkspaceRegexPermissionRepository                          │
│  + NEW: WorkspaceGroupRegexPermissionRepository                     │
│  DB: + workspace_regex_permissions                                  │
│      + workspace_group_regex_permissions                             │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                     React SPA (Frontend)                             │
│  + NEW: WorkspaceContext + WorkspaceProvider                         │
│  + NEW: WorkspacePicker in Header                                    │
│  + MODIFIED: http.ts injects X-MLFLOW-WORKSPACE header              │
│  + NEW: Workspace CRUD UI (create/update/delete forms)               │
│  + MODIFIED: All admin pages consume workspace context                │
└─────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Current State | v1.1 Change | Change Type |
|-----------|--------------|-------------|-------------|
| `routers/__init__.py` | 15 routers registered | Register `workspace_router` (16th) | MODIFY |
| `routers/workspace.py` | Does not exist | New router proxying CRUD to MLflow upstream | NEW |
| `routers/workspace_permissions.py` | 8 endpoints (user/group CRUD) | Add 8 regex/group-regex endpoints | MODIFY |
| `validators/workspace.py` | Admin-only for update/delete | MANAGE delegation: admin OR workspace MANAGE | MODIFY |
| `hooks/after_request.py` | `_filter_search_experiments` checks `can_read_experiment` only | Add workspace membership filter | MODIFY |
| `utils/workspace_cache.py` | Lookup: implicit default → user → group | Add regex → group-regex sources | MODIFY |
| `db/models/workspace.py` | `SqlWorkspacePermission`, `SqlWorkspaceGroupPermission` | Add `SqlWorkspaceRegexPermission`, `SqlWorkspaceGroupRegexPermission` | MODIFY |
| `entities/workspace.py` | `WorkspacePermission`, `WorkspaceGroupPermission` | Add regex + group-regex entity classes | MODIFY |
| `repository/` | Standalone workspace user/group repos | Add regex/group-regex repos extending base classes | NEW files |
| `sqlalchemy_store.py` | Workspace user/group store methods | Add regex/group-regex methods, workspace CRUD proxying methods | MODIFY |
| `dependencies.py` | `check_workspace_manage_permission`, `check_workspace_read_permission` | No change needed (existing deps sufficient) | UNCHANGED |
| `middleware/auth_middleware.py` | Sets `AuthContext(username, is_admin, workspace)` | No change needed | UNCHANGED |
| `bridge/user.py` | `get_request_workspace()` exists | No change needed | UNCHANGED |
| Frontend `http.ts` | No workspace header injection | Inject `X-MLFLOW-WORKSPACE` from workspace context | MODIFY |
| Frontend `header.tsx` | No workspace picker | Add `WorkspacePicker` component | MODIFY |
| Frontend `user-provider.tsx` | UserContext only | WorkspaceProvider wraps app | NEW (context) |
| Frontend `workspace-service.ts` | List + permission fetchers | Add CRUD methods (create, update, delete) | MODIFY |

## Recommended Project Structure

### New/Modified Backend Files

```
mlflow_oidc_auth/
├── routers/
│   ├── workspace.py                     # NEW: workspace CRUD proxy router (5 endpoints)
│   ├── workspace_permissions.py         # MODIFY: add regex + group-regex endpoints
│   ├── _prefix.py                       # MODIFY: add WORKSPACE_ROUTER_PREFIX
│   └── __init__.py                      # MODIFY: register workspace_router
├── validators/
│   └── workspace.py                     # MODIFY: MANAGE delegation for update/delete
├── hooks/
│   └── after_request.py                 # MODIFY: workspace-scoped search filtering
├── utils/
│   └── workspace_cache.py              # MODIFY: add regex/group-regex lookup
├── db/
│   ├── models/
│   │   └── workspace.py                 # MODIFY: add SqlWorkspaceRegexPermission,
│   │                                    #         SqlWorkspaceGroupRegexPermission
│   └── migrations/
│       └── versions/
│           └── xxxx_add_workspace_regex_permissions.py  # NEW: Alembic migration
├── entities/
│   └── workspace.py                     # MODIFY: add regex + group-regex entities
├── models/
│   └── workspace.py                     # MODIFY: add Pydantic models for CRUD + regex
├── repository/
│   ├── workspace_regex_permission.py          # NEW: extends BaseRegexPermissionRepository
│   └── workspace_group_regex_permission.py    # NEW: extends BaseGroupRegexPermissionRepository
├── sqlalchemy_store.py                  # MODIFY: add workspace regex methods
└── store.py                             # MODIFY: expose new store methods
```

### New/Modified Frontend Files

```
web-react/src/
├── core/
│   ├── context/
│   │   ├── workspace-provider.tsx       # NEW: WorkspaceContext + WorkspaceProvider
│   │   └── use-workspace.ts             # NEW: useWorkspace hook
│   ├── services/
│   │   ├── http.ts                      # MODIFY: inject X-MLFLOW-WORKSPACE header
│   │   └── workspace-service.ts         # MODIFY: add CRUD fetchers
│   └── configs/
│       └── api-endpoints.ts             # MODIFY: add workspace CRUD endpoints
├── shared/
│   ├── components/
│   │   ├── header.tsx                   # MODIFY: add WorkspacePicker
│   │   └── workspace-picker.tsx         # NEW: dropdown component
│   └── types/
│       └── entity.ts                    # MODIFY: add workspace CRUD types
├── features/
│   └── workspaces/
│       ├── workspaces-page.tsx          # MODIFY: add create/delete workspace actions
│       ├── workspace-detail-page.tsx    # MODIFY: add update/delete workspace actions
│       └── components/
│           ├── workspace-create-form.tsx     # NEW
│           ├── workspace-edit-form.tsx       # NEW
│           └── workspace-delete-dialog.tsx   # NEW
└── app.tsx                              # No change (routes already exist)
```

### Structure Rationale

- **`routers/workspace.py` as separate new router (not merged into workspace_permissions.py):** Workspace CRUD proxy handles workspace *lifecycle* (create/list/get/update/delete workspace entities). Workspace permissions handles *access control*. Different concerns, different URL prefixes (`/api/3.0/mlflow/workspaces` vs `/api/3.0/mlflow/permissions/workspaces`). This also matches the split upstream MLflow has between workspace RPCs and workspace permission RPCs.
- **Regex repos use base classes (unlike standalone workspace repos):** The existing standalone `WorkspacePermissionRepository` and `WorkspaceGroupPermissionRepository` were intentionally standalone because workspace is a tenant boundary, not a typical resource (decision WSAUTH-B). However, regex workspace permissions behave identically to regex permissions for any other resource type — they have `regex`, `priority`, `permission`, and `user_id`/`group_id` columns. Using `BaseRegexPermissionRepository` and `BaseGroupRegexPermissionRepository` avoids re-implementing the same grant/get/list/update/revoke logic.
- **Frontend `workspace-provider.tsx` as separate context (not extending UserProvider):** Workspace selection is orthogonal to user identity. A user's workspace choice changes frequently during a session; their identity doesn't. Separate contexts mean workspace changes don't re-render components that only care about user identity.
- **`http.ts` modification for header injection:** The `http()` function is the single point where all API calls flow through. Adding the workspace header here means every API call automatically includes workspace context. The alternative (each service adding the header) is error-prone and violates DRY.

## Architectural Patterns

### Pattern 1: FastAPI Proxy Router for Upstream Workspace CRUD

**What:** A new FastAPI router that intercepts workspace CRUD requests, performs auth checks, then forwards them to MLflow's Flask app via an internal HTTP call (or by letting the request fall through to Flask via the WSGI bridge).

**When to use:** For all workspace lifecycle operations (create, list, get, update, delete) where the plugin needs to enforce authorization but doesn't own the data.

**Trade-offs:**
- Pro: Plugin controls who can create/update/delete workspaces without duplicating upstream logic; clean separation of auth from lifecycle
- Pro: Upstream MLflow handles actual workspace storage and validation
- Con: Creates a request hop (FastAPI → internal HTTP → Flask); adds latency
- Con: If upstream response format changes, proxy must adapt

**Recommended approach — passthrough with FastAPI dependency guards:**

```python
# mlflow_oidc_auth/routers/workspace.py
from fastapi import APIRouter, Depends, Request, Response
from mlflow_oidc_auth.dependencies import check_admin_permission, check_workspace_manage_permission
from mlflow_oidc_auth.routers._prefix import WORKSPACE_ROUTER_PREFIX

workspace_router = APIRouter(prefix=WORKSPACE_ROUTER_PREFIX)

@workspace_router.post("")
async def create_workspace(
    request: Request,
    _=Depends(check_admin_permission),
):
    """Proxy workspace creation to MLflow upstream. Admin-only."""
    # Forward the request body to MLflow's Flask app via httpx
    # MLflow's Flask app at the same path handles the actual creation
    ...

@workspace_router.put("/{workspace_name}")
async def update_workspace(
    workspace_name: str,
    request: Request,
    _=Depends(check_workspace_manage_permission),  # Admin OR MANAGE
):
    """Proxy workspace update. Admin or workspace MANAGE."""
    ...

@workspace_router.delete("/{workspace_name}")
async def delete_workspace(
    workspace_name: str,
    request: Request,
    _=Depends(check_workspace_manage_permission),  # Admin OR MANAGE
):
    """Proxy workspace deletion. Admin or workspace MANAGE."""
    ...
```

**Why NOT let requests fall through to Flask:** Workspace CRUD requests currently pass through the Flask `before_request` hook which maps them to validators. This works for authorization but doesn't give us the ability to intercept the *response* (e.g., auto-grant MANAGE on workspace creation) cleanly. A FastAPI proxy router gives us pre- and post-processing control.

**Alternative considered — before_request only:** Keep workspace CRUD flowing through Flask with `before_request` validators (already working). Problem: validators can only block/allow, they can't modify response or trigger side effects easily. The FastAPI router approach is more capable.

**Recommended: Hybrid approach.** Keep the existing before_request validators as a safety net. Add FastAPI router as the primary entry point for workspace CRUD from the admin UI. The admin UI calls the FastAPI router directly; the MLflow SDK clients still hit Flask via passthrough.

### Pattern 2: Workspace-Scoped Search Filtering via Experiment→Workspace Mapping

**What:** Enhance `_filter_search_experiments()` and `_filter_search_registered_models()` in `after_request.py` to additionally filter results based on workspace membership, not just resource-level permissions.

**When to use:** When workspaces are enabled and the user's request has workspace context.

**Trade-offs:**
- Pro: Users only see resources belonging to workspaces they have access to
- Pro: Builds on existing filtering infrastructure
- Con: Requires knowing which workspace an experiment/model belongs to — this mapping lives in MLflow's workspace store, not our DB
- Con: Additional latency per search result

**The key challenge: experiment→workspace mapping.** The plugin doesn't store which experiments belong to which workspaces. Upstream MLflow does. Two approaches:

**Approach A — Filter on workspace permission only (simpler, recommended):**

The existing `can_read_experiment()` already resolves through the workspace fallback chain. If a user has no resource-level permission and no workspace permission, `resolve_permission()` returns `NO_PERMISSIONS`. This means `can_read_experiment()` already returns `false` for experiments in workspaces the user can't access, **as long as the workspace context is correctly set in the request**.

The real gap is: what if the user lists experiments without a workspace header (or with "default")? They could see experiments from other workspaces if those experiments have no explicit resource-level permissions that deny access.

**Solution:** In `_filter_search_experiments()`, resolve each experiment's workspace (from upstream) and check that the user has permission for *that* workspace, not just the request's workspace header.

```python
# Conceptual — in after_request.py _filter_search_experiments()
def _filter_search_experiments(resp: Response):
    if get_fastapi_admin_status():
        return
    # ... existing filtering ...
    
    if config.MLFLOW_ENABLE_WORKSPACES:
        auth_context = get_auth_context()
        for e in list(response_message.experiments):
            exp_workspace = _get_experiment_workspace(e.experiment_id)
            if exp_workspace and get_workspace_permission_cached(
                auth_context.username, exp_workspace
            ) is None:
                response_message.experiments.remove(e)
```

**Approach B — Rely on existing permission resolution (do nothing extra):**

If the permission resolution chain already returns `NO_PERMISSIONS` for resources in workspaces the user can't access, then `can_read_experiment()` handles it. **This is the case when workspace fallback returns `workspace-deny`.**

Looking at the code: when `resolve_permission()` finds `result.kind == "fallback"` and workspaces are enabled, it checks workspace permission. If no workspace permission, it returns `PermissionResult(NO_PERMISSIONS, "workspace-deny")`. This means `can_read_experiment()` → `permission.can_read` → `False`.

**But there's a subtlety:** the workspace fallback uses `get_request_workspace()` (the *requester's* active workspace), not the experiment's actual workspace. If user is browsing "default" workspace but an experiment belongs to "team-alpha" with no explicit permissions, the fallback checks "default" workspace permission (which they have) and grants access — **data leakage**.

**Conclusion: Approach A is necessary.** We must check the experiment's *own* workspace, not just the request workspace.

**How to get experiment→workspace mapping:** MLflow upstream's `get_experiment()` response includes workspace info (the `workspace` field on the experiment proto). The `_filter_search_experiments()` function already has the experiment proto objects in hand — check if they have a workspace field.

### Pattern 3: Regex Workspace Permissions via Base Repository Classes

**What:** Add regex-based workspace permissions following the same 4-variant pattern used by all other resource types: user-regex and group-regex. Use the existing `BaseRegexPermissionRepository` and `BaseGroupRegexPermissionRepository` base classes.

**When to use:** When organizations want pattern-based workspace access (e.g., "grant READ to all workspaces matching `team-*`").

**Trade-offs:**
- Pro: Consistent with all other resource types; proven pattern
- Pro: Base classes already handle grant/get/list/update/revoke — minimal new code
- Pro: Enables bulk workspace provisioning via patterns
- Con: Adds 2 new DB tables + migration
- Con: Workspace cache must add regex/group-regex lookup

**Example — new repo using base class:**

```python
# mlflow_oidc_auth/repository/workspace_regex_permission.py
from mlflow_oidc_auth.db.models.workspace import SqlWorkspaceRegexPermission
from mlflow_oidc_auth.entities.workspace import WorkspaceRegexPermission
from mlflow_oidc_auth.repository._base import BaseRegexPermissionRepository

class WorkspaceRegexPermissionRepository(
    BaseRegexPermissionRepository[SqlWorkspaceRegexPermission, WorkspaceRegexPermission]
):
    model_class = SqlWorkspaceRegexPermission
```

**Integration into workspace cache:**

```python
# In workspace_cache.py _lookup_workspace_permission()
def _lookup_workspace_permission(username: str, workspace: str) -> Permission | None:
    # 1. Implicit default workspace (existing)
    if workspace == "default" and config.GRANT_DEFAULT_WORKSPACE_ACCESS:
        return MANAGE

    # 2. User-level direct (existing)
    try:
        perm = store.get_workspace_permission(workspace, username)
        return get_permission(perm.permission)
    except Exception:
        pass

    # 3. Group-level direct (existing)
    try:
        perm = store.get_user_groups_workspace_permission(workspace, username)
        return get_permission(perm.permission)
    except Exception:
        pass

    # 4. User-regex (NEW)
    try:
        regexes = store.list_workspace_regex_permissions(username)
        perm = _match_regex_permission(regexes, workspace, "workspace")
        return get_permission(perm)
    except Exception:
        pass

    # 5. Group-regex (NEW)
    try:
        group_ids = store.get_groups_ids_for_user(username)
        regexes = store.list_group_workspace_regex_permissions_for_groups_ids(group_ids)
        perm = _match_regex_permission(regexes, workspace, "workspace")
        return get_permission(perm)
    except Exception:
        pass

    return None
```

### Pattern 4: Global Workspace Picker via React Context + HTTP Header Injection

**What:** A `WorkspaceContext` that holds the user's currently selected workspace. A `WorkspacePicker` dropdown in the header. The `http()` utility automatically injects `X-MLFLOW-WORKSPACE` header based on context value.

**When to use:** When workspaces are enabled (`workspacesEnabled` in RuntimeConfig).

**Trade-offs:**
- Pro: All API calls automatically scoped — no per-service modification needed
- Pro: Workspace selection persists across page navigation
- Con: Context change triggers re-renders of consuming components — must memoize carefully
- Con: Need to handle workspace list loading at app startup

**Implementation sketch:**

```typescript
// core/context/workspace-provider.tsx
import { createContext, useContext, useState, useEffect, type ReactNode } from "react";
import { fetchAllWorkspaces } from "../services/workspace-service";
import { useRuntimeConfig } from "../context/use-runtime-config";

interface WorkspaceContextValue {
  activeWorkspace: string | null;
  setActiveWorkspace: (ws: string) => void;
  workspaces: string[];
  isLoading: boolean;
}

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const config = useRuntimeConfig();
  const [activeWorkspace, setActiveWorkspace] = useState<string | null>(null);
  const [workspaces, setWorkspaces] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!config.workspacesEnabled) {
      setIsLoading(false);
      return;
    }
    fetchAllWorkspaces()
      .then((resp) => {
        const names = resp.workspaces.map((ws) => ws.name);
        setWorkspaces(names);
        setActiveWorkspace(names[0] ?? "default");
      })
      .finally(() => setIsLoading(false));
  }, [config.workspacesEnabled]);

  return (
    <WorkspaceContext value={{
      activeWorkspace,
      setActiveWorkspace,
      workspaces,
      isLoading,
    }}>
      {children}
    </WorkspaceContext>
  );
}

export function useWorkspace() {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) throw new Error("useWorkspace must be used within WorkspaceProvider");
  return ctx;
}
```

```typescript
// core/services/http.ts — MODIFIED
// Add workspace header injection
import { getActiveWorkspace } from "../context/workspace-store";

export async function http<T = unknown>(
  url: string,
  options: RequestOptions = {},
): Promise<T> {
  const { params, ...rest } = options;
  const workspace = getActiveWorkspace(); // module-level getter
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(rest.headers || {}),
  };
  if (workspace) {
    headers["X-MLFLOW-WORKSPACE"] = workspace;
  }
  const res = await fetch(buildUrl(url, params), {
    ...rest,
    headers,
    credentials: "include",
  });
  // ... rest unchanged
}
```

**Challenge with React Context + module-level http.ts:** The `http()` function is a plain module, not a React component — it can't use `useContext()`. Two solutions:

1. **Module-level store (recommended):** A tiny module that holds the active workspace value, updated by `WorkspaceProvider` via a setter. `http.ts` reads from this module.
2. **Pass header per-call:** Each service explicitly passes workspace. Violates DRY.

```typescript
// core/context/workspace-store.ts — module-level state (NOT React context)
let _activeWorkspace: string | null = null;

export function setActiveWorkspace(ws: string | null) {
  _activeWorkspace = ws;
}
export function getActiveWorkspace(): string | null {
  return _activeWorkspace;
}
```

The `WorkspaceProvider` calls `setActiveWorkspace()` whenever the context value changes, keeping the module-level state in sync with React state.

## Data Flow

### Workspace CRUD Request Flow (NEW)

```
Admin UI: "Create Workspace"
    ↓
POST /api/3.0/mlflow/workspaces (to FastAPI)
    ↓
workspace_router.create_workspace()
    → Depends(check_admin_permission) ← FastAPI dependency
    → Forward request body to MLflow Flask app
    ↓
MLflow Flask app processes workspace creation
    ↓
FastAPI router receives response
    → Auto-grant MANAGE to creator (store.create_workspace_permission)
    → Invalidate workspace cache if needed
    → Return response to client
```

```
Admin UI: "Update Workspace"
    ↓
PUT /api/3.0/mlflow/workspaces/{name} (to FastAPI)
    ↓
workspace_router.update_workspace()
    → Depends(check_workspace_manage_permission) ← Admin OR MANAGE
    → Forward to MLflow Flask app
    ↓
Response back to client
```

### Workspace-Scoped Search Filtering (MODIFIED)

```
MLflow SDK: SearchExperiments()
    ↓
Flask after_request_hook → _filter_search_experiments()
    ↓
For each experiment in response:
    1. can_read_experiment(experiment_id, username)  ← EXISTING
       → resolve_permission() → resource → workspace fallback → default
    2. IF workspaces enabled:                        ← NEW
       experiment_workspace = experiment.tags.get("workspace") or infer
       user_has_workspace_access = get_workspace_permission_cached(
           username, experiment_workspace
       )
       if not user_has_workspace_access:
           remove experiment from response
    ↓
Filtered response back to client
```

### Regex Workspace Permission Resolution (MODIFIED)

```
get_workspace_permission_cached(username, workspace_name)
    ↓
Cache miss → _lookup_workspace_permission()
    ↓
1. Is "default" workspace + GRANT_DEFAULT_WORKSPACE_ACCESS?  ← EXISTING
   → Return MANAGE
    ↓
2. User-level: store.get_workspace_permission()              ← EXISTING
   → Found? Return permission
    ↓
3. Group-level: store.get_user_groups_workspace_permission() ← EXISTING
   → Found? Return highest permission
    ↓
4. User-regex: store.list_workspace_regex_permissions()      ← NEW
   → Any regex matches workspace_name? Return permission
    ↓
5. Group-regex: store.list_group_workspace_regex_permissions() ← NEW
   → Any regex matches workspace_name? Return permission
    ↓
6. None found → Return None (no workspace access)
```

### Global Workspace Picker State Flow (NEW)

```
App loads → RuntimeConfig → workspacesEnabled?
    ↓ YES
WorkspaceProvider mounts
    → fetchAllWorkspaces() (filtered by user permissions via after_request)
    → setWorkspaces([...])
    → setActiveWorkspace(first workspace or "default")
    → setActiveWorkspace also calls workspace-store.setActiveWorkspace()
    ↓
Header renders WorkspacePicker
    → Shows dropdown with workspace names
    → On selection: setActiveWorkspace(newWorkspace)
    → workspace-store synced, http.ts reads new value
    ↓
All subsequent API calls from admin UI
    → http() reads getActiveWorkspace()
    → Adds X-MLFLOW-WORKSPACE header to every request
    ↓
Backend receives request with workspace context
    → Permission resolution uses workspace from header
    → Search results filtered by workspace
    → Admin pages show workspace-scoped data
```

### Key Data Flows

1. **Workspace CRUD:** Admin UI → FastAPI proxy router → auth check → forward to MLflow Flask → response → auto-grant MANAGE → return to UI
2. **Search filtering:** MLflow returns all results → after_request checks both resource permissions AND workspace membership → removes unauthorized experiments/models
3. **Regex workspace access:** User has no direct workspace permission → cache checks user-regex patterns → "team-.*" matches "team-alpha" → grants READ
4. **Workspace picker:** User selects workspace in header → module-level store updated → all API calls include new workspace header → backend scopes all responses

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 1-10 workspaces | No special handling. TTLCache handles the few lookups. Regex workspace permissions are low-value (just use direct grants). |
| 10-100 workspaces | Regex workspace permissions become valuable (pattern-match "team-*" instead of 50 individual grants). Cache benefits grow. Consider DB index on workspace_regex_permissions.regex column. |
| 100+ workspaces | Workspace picker dropdown becomes unwieldy — needs search/filter UI. Regex permissions are essential for manageability. Experiment→workspace mapping lookups in after_request become a bottleneck — consider batch lookup or cache. |

### Scaling Priorities

1. **First bottleneck — after_request experiment→workspace lookups:** In `_filter_search_experiments()`, if we need to check each experiment's workspace, that's N queries per search page. **Mitigation:** Batch lookup (get all experiment workspaces in one query) or cache experiment→workspace mapping. Upstream MLflow may expose a batch API for this.
2. **Second bottleneck — workspace picker API call on app load:** `fetchAllWorkspaces()` with user filtering. With 100+ workspaces, the filtered list scan in `_filter_list_workspaces()` touches every workspace. **Mitigation:** DB-side filtering (query only workspaces where user has permission) instead of fetch-all-then-filter.

## Anti-Patterns

### Anti-Pattern 1: Workspace CRUD Router That Duplicates MLflow's Workspace Store

**What people do:** Create workspace entities in the plugin's own database, maintaining a parallel workspace store that duplicates MLflow's upstream `_get_workspace_store()`.
**Why it's wrong:** Two sources of truth for workspace existence. If upstream MLflow adds or removes a workspace (e.g., via API, migration), the plugin's copy is stale. Creates sync nightmares.
**Do this instead:** Plugin manages workspace *permissions* only. Workspace *existence* (create/list/get/update/delete) is proxied to upstream MLflow. The plugin's DB has `workspace_permissions`, `workspace_group_permissions`, etc. — but no `workspaces` table.

### Anti-Pattern 2: Filtering Experiments by Request Workspace Header Only

**What people do:** In `_filter_search_experiments()`, check workspace permission using only `get_request_workspace()` (the X-MLFLOW-WORKSPACE header value).
**Why it's wrong:** If the user searches without a workspace header (or with "default"), they could see experiments from any workspace, as long as those experiments have no explicit deny permissions. The header represents the user's *requested* scope, not the experiment's *actual* workspace.
**Do this instead:** For each experiment in results, determine the experiment's actual workspace (from its tags or upstream metadata) and check workspace permission for *that* workspace. This prevents cross-workspace data leakage.

### Anti-Pattern 3: Workspace Picker That Re-renders the Entire App

**What people do:** Use React Context for workspace state and have every component consume it via `useContext`.
**Why it's wrong:** Changing the workspace re-renders all consuming components simultaneously. With many admin pages and data tables, this causes a visible UI freeze.
**Do this instead:** Use a module-level store for the workspace value (not React Context for the actual value). React Context provides the setter + workspace list. Individual pages react to workspace changes via their own data-fetching hooks, which trigger on workspace change. This decouples re-render scope.

### Anti-Pattern 4: Adding Regex Workspace Permissions Without Using Base Classes

**What people do:** Implement `WorkspaceRegexPermissionRepository` from scratch with custom grant/get/list/update/revoke methods.
**Why it's wrong:** Duplicates ~300 lines of proven code from `BaseRegexPermissionRepository`. Inconsistencies between workspace regex and other resource regex repos become maintenance burden.
**Do this instead:** Extend `BaseRegexPermissionRepository[SqlWorkspaceRegexPermission, WorkspaceRegexPermission]`. Override nothing unless workspace-specific behavior is needed. The base class handles everything via `model_class` class attribute.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| MLflow Workspace API (`/api/3.0/mlflow/workspaces`) | FastAPI proxy router forwards CRUD requests | `PUBLIC_UNDOCUMENTED` API — monitor for breaking changes. Plugin adds auth layer on top. |
| MLflow Experiment Store | Query experiment→workspace mapping in after_request | Needed for workspace-scoped search filtering. May need to use `_get_tracking_store().get_experiment()` or inspect experiment tags. |
| MLflow Model Registry Store | Query model→workspace mapping in after_request | Same pattern as experiments. Check if `registered_model.tags` contains workspace info. |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| workspace_router → MLflow Flask | Internal HTTP (httpx) or WSGI bridge | FastAPI router proxies requests. Must preserve request headers including auth cookies. Use `httpx.AsyncClient` with `base_url` pointing to internal Flask app. |
| after_request → workspace cache | Python function call | `get_workspace_permission_cached()` called per-experiment during search filtering. Hot path — cache is critical. |
| workspace cache → regex repos | Python function call | New lookup steps for regex/group-regex. Same exception-based flow as direct lookups. |
| WorkspaceProvider → workspace-store module | `setActiveWorkspace()` | Sync React state to module-level state so `http.ts` can read it without React Context. |
| WorkspacePicker → WorkspaceProvider | `setActiveWorkspace()` via context | User selection updates both React context and module-level store. |
| http.ts → workspace-store | `getActiveWorkspace()` | Every API call reads module-level workspace. No React dependency. |
| workspace_permissions_router → store | Python function call | Existing pattern. New regex/group-regex endpoints follow exact same pattern as other resource regex permissions. |

## Build Order Implications

Based on architecture analysis and dependency chains, the recommended build order within v1.1:

### Step 1: Regex Workspace Permissions (Backend Foundation)

**Build:** DB models, Alembic migration, entity classes, repository classes (extending bases), store methods, router endpoints on `workspace_permissions_router`, workspace cache integration.

**Rationale:** This is a pure backend additive change with zero impact on existing functionality. The new tables and repos follow established patterns exactly. Once merged, the permission resolution chain becomes complete (all 4 source types for workspaces). All subsequent steps benefit from having regex workspace permissions available.

**Files touched:**
- `db/models/workspace.py` (add 2 ORM models)
- `db/migrations/versions/` (1 new migration)
- `entities/workspace.py` (add 2 entity classes)
- `models/workspace.py` (add Pydantic models for regex)
- `repository/workspace_regex_permission.py` (NEW)
- `repository/workspace_group_regex_permission.py` (NEW)
- `sqlalchemy_store.py` (add regex workspace methods)
- `store.py` (expose methods)
- `utils/workspace_cache.py` (add regex/group-regex lookup)
- `routers/workspace_permissions.py` (add 8 regex endpoints)

### Step 2: Workspace Validators + MANAGE Delegation

**Build:** Modify `validate_can_update_workspace()` and `validate_can_delete_workspace()` to check MANAGE permission (not admin-only).

**Rationale:** Small, focused change. Required before the CRUD proxy router can allow non-admin workspace management. Depends on workspace cache (Step 1) being complete with regex lookup for full permission resolution.

**Files touched:**
- `validators/workspace.py` (modify 2 functions)

### Step 3: Workspace CRUD Proxy Router

**Build:** New `routers/workspace.py` with 5 endpoints (create, list, get, update, delete). Router prefix. Registration in `__init__.py`. Auto-grant MANAGE on creation.

**Rationale:** Depends on Step 2 (MANAGE delegation) for update/delete auth. Creates the backend API surface that the frontend will consume. Can be tested via HTTP without frontend.

**Files touched:**
- `routers/workspace.py` (NEW)
- `routers/_prefix.py` (add prefix constant)
- `routers/__init__.py` (register router)

### Step 4: Workspace-Scoped Search Filtering

**Build:** Modify `_filter_search_experiments()`, `_filter_search_registered_models()`, and `_filter_search_logged_models()` to check experiment/model workspace membership.

**Rationale:** Depends on workspace cache (Step 1) being complete. This is the security-critical change — without it, cross-workspace data leakage is possible. Needs investigation of how upstream MLflow exposes experiment→workspace mapping.

**Files touched:**
- `hooks/after_request.py` (modify 3 filter functions)

**Research flag:** How does upstream MLflow expose experiment→workspace mapping in the proto response? Need to inspect experiment proto fields or tags. If not available in the search response, may need a separate batch lookup — significant performance concern.

### Step 5: Global Workspace Picker (Frontend)

**Build:** `WorkspaceProvider`, `workspace-store.ts`, `WorkspacePicker` component, `http.ts` header injection, workspace CRUD forms.

**Rationale:** Depends on Steps 3 (CRUD proxy) and 4 (scoped filtering) for a complete backend. Pure frontend change once backend is ready. Can be developed in parallel with Steps 3-4 using mock data.

**Files touched:**
- `core/context/workspace-provider.tsx` (NEW)
- `core/context/workspace-store.ts` (NEW)
- `core/context/use-workspace.ts` (NEW)
- `core/services/http.ts` (modify)
- `core/services/workspace-service.ts` (modify)
- `core/configs/api-endpoints.ts` (modify)
- `shared/components/header.tsx` (modify)
- `shared/components/workspace-picker.tsx` (NEW)
- `shared/types/entity.ts` (modify)
- `features/workspaces/workspaces-page.tsx` (modify)
- `features/workspaces/workspace-detail-page.tsx` (modify)
- `features/workspaces/components/workspace-create-form.tsx` (NEW)
- `features/workspaces/components/workspace-edit-form.tsx` (NEW)
- `features/workspaces/components/workspace-delete-dialog.tsx` (NEW)

### Dependency Graph

```
Step 1: Regex Workspace Permissions
    ↓
Step 2: MANAGE Delegation (depends on Step 1 for full resolution)
    ↓
Step 3: CRUD Proxy Router (depends on Step 2 for update/delete auth)
    │
    ├── Step 4: Search Filtering (depends on Step 1, independent of Step 3)
    │
    └── Step 5: Frontend (depends on Steps 3 + 4 for complete backend)
```

Steps 3 and 4 can be built in parallel after Step 2.
Step 5 can begin in parallel with Steps 3-4 using mock data, but final integration requires them.

## Sources

- Direct codebase analysis: all files listed in component responsibilities table
- Existing v1.0 architecture research: `.planning/research/ARCHITECTURE.md` (previous version)
- PROJECT.md constraints and decisions: `.planning/PROJECT.md`
- MLflow 3.10 workspace protobuf RPCs: `CreateWorkspace`, `GetWorkspace`, `ListWorkspaces`, `UpdateWorkspace`, `DeleteWorkspace`
- Repository base classes: `mlflow_oidc_auth/repository/_base.py` (4 generic bases)
- Permission resolution: `mlflow_oidc_auth/utils/permissions.py` (PERMISSION_REGISTRY, resolve_permission)
- Workspace cache: `mlflow_oidc_auth/utils/workspace_cache.py` (TTLCache, lookup order)
- After-request hooks: `mlflow_oidc_auth/hooks/after_request.py` (search filtering patterns)
- Frontend HTTP layer: `web-react/src/core/services/http.ts`
- Frontend workspace service: `web-react/src/core/services/workspace-service.ts`
- Frontend header component: `web-react/src/shared/components/header.tsx`
- Confidence: HIGH — all recommendations based on direct source code analysis of existing codebase patterns

---
*Architecture research for: v1.1 workspace CRUD management, scoped search filtering, regex workspace permissions, and global workspace picker*
*Researched: 2026-03-24*
