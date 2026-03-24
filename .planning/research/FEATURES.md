# Feature Landscape

**Domain:** Workspace lifecycle management, admin UI enhancements, and regex workspace permissions for mlflow-oidc-auth plugin
**Researched:** 2026-03-24
**Milestone:** v1.1 Workspace Management

## Context: What's Already Built (v1.0 Foundation)

The v1.0 milestone delivered workspace permission infrastructure. What exists today:

| Component | Status | Implementation |
|-----------|--------|----------------|
| Feature flag (`MLFLOW_ENABLE_WORKSPACES`) | ✅ Built | `config.py` — defaults to `false` |
| `X-MLFLOW-WORKSPACE` header propagation | ✅ Built | `AuthContext` frozen dataclass, `AuthAwareWSGIMiddleware` |
| Workspace permission DB tables | ✅ Built | `workspace_permissions` + `workspace_group_permissions` (Alembic migration) |
| Default workspace seeding | ✅ Built | `_seed_default_workspace()` in `app.py` startup |
| `GRANT_DEFAULT_WORKSPACE_ACCESS` config | ✅ Built | Implicit MANAGE on "default" workspace via TTLCache |
| before_request handlers for 5 workspace RPCs | ✅ Built | `CreateWorkspace` (admin), `GetWorkspace` (READ), `ListWorkspaces` (all), `UpdateWorkspace` (admin), `DeleteWorkspace` (admin) |
| Workspace permission data layer | ✅ Built | Entities, repos (`WorkspacePermissionRepository`, `WorkspaceGroupPermissionRepository`), ORM models, store methods |
| TTLCache for workspace permission lookups | ✅ Built | `workspace_cache.py` — lazy init, configurable size/TTL |
| CreateExperiment/CreateRegisteredModel workspace gating | ✅ Built | `_is_workspace_gated_creation()` in before_request |
| Permission resolution workspace fallback | ✅ Built | Resource → workspace → NO_PERMISSIONS chain |
| Workspace user permission CRUD (8 endpoints) | ✅ Built | FastAPI router at `/api/3.0/mlflow/permissions/workspaces/{workspace}/{users,groups}` |
| Workspace group permission CRUD | ✅ Built | Same router, group variants |
| MANAGE delegation | ✅ Built | Workspace MANAGE users can grant sub-admin |
| React workspace list/detail/member pages | ✅ Built | `workspaces-page.tsx`, `workspace-detail-page.tsx`, `workspace-members-section.tsx` |
| OIDC workspace claim mapping | ✅ Built | Plugin/JWT/auto-assign via `OIDC_WORKSPACE_DETECTION_PLUGIN` |
| ListWorkspaces after_request filtering | ✅ Built | `_filter_list_workspaces()` — filters by user permission |

## What v1.1 Needs to Add

The v1.1 milestone fills **five remaining gaps**:

1. **Workspace CRUD backend** — FastAPI proxy to MLflow's native workspace REST API
2. **Workspace management UI** — Admin page for creating/viewing/updating/deleting workspaces
3. **Global workspace picker** — Dropdown in UI header scoping all admin pages
4. **Workspace-scoped search result filtering** — after_request hooks filter experiments/models by workspace
5. **Regex workspace permissions** — Pattern-based workspace access rules

## Table Stakes

Features that complete the workspace story. Missing = workspace management is incomplete and admins must use raw API calls.

### TS-01: Workspace CRUD Backend (FastAPI Proxy)

| Aspect | Detail |
|--------|--------|
| **Why Expected** | Admins need to create/list/get/update/delete workspaces through the plugin. Currently, workspace CRUD only works via MLflow's native Flask endpoints (which the before_request hooks already gate). The admin UI needs dedicated FastAPI endpoints that proxy to MLflow's upstream API with proper auth checks. |
| **Complexity** | Medium |
| **Depends On** | Existing before_request validators (v1.0), MLflow's workspace protobuf handlers |

**Expected Behavior:**

| Operation | Endpoint | Auth Requirement | Upstream MLflow Endpoint |
|-----------|----------|-----------------|--------------------------|
| Create | `POST /oidc/workspaces` | Admin only | `POST /api/3.0/mlflow/workspaces` |
| List | `GET /oidc/workspaces` | All authenticated (filtered) | `GET /api/3.0/mlflow/workspaces` |
| Get | `GET /oidc/workspaces/{name}` | Any workspace permission | `GET /api/3.0/mlflow/workspaces/{workspace_name}` |
| Update | `PATCH /oidc/workspaces/{name}` | Admin only | `PATCH /api/3.0/mlflow/workspaces/{workspace_name}` |
| Delete | `DELETE /oidc/workspaces/{name}` | Admin only | `DELETE /api/3.0/mlflow/workspaces/{workspace_name}` |

**MLflow Workspace Naming Rules** (HIGH confidence — verified from `WorkspaceNameValidator` source):
- Pattern: `^(?!.*--)[a-z0-9]([-a-z0-9]*[a-z0-9])?$` (DNS-safe, lowercase alphanumeric + hyphens)
- Length: 2-63 characters
- Reserved names: `workspaces`, `api`, `ajax-api`, `static-files`
- No consecutive hyphens (`--`)
- Must start and end with alphanumeric

**MLflow Workspace Deletion Modes** (HIGH confidence — from `WorkspaceDeletionMode` enum):
- `RESTRICT` (default): Refuse if workspace still contains resources
- `SET_DEFAULT`: Reassign resources to default workspace
- `CASCADE`: Delete all resources in workspace

**Proxy Architecture Decision:** The plugin should NOT bypass MLflow's workspace store. Instead, the FastAPI router should make internal HTTP calls to the MLflow Flask endpoints (already mounted at `/`). This ensures MLflow handles all workspace lifecycle logic (naming validation, deletion constraints, artifact root management) while the plugin controls only authorization.

**Implementation Pattern:** Use `httpx.AsyncClient` to call the mounted Flask app's workspace endpoints. The before_request hooks already enforce auth on the Flask side, so the FastAPI proxy needs to:
1. Validate the caller is authorized (admin for CUD, any auth for list/get)
2. Forward the request to MLflow's workspace API
3. Return the response (possibly enriching it with permission data)

**Alternative Pattern:** Since Flask is mounted under FastAPI via `AuthAwareWSGIMiddleware`, the proxy could also use the internal store directly. However, proxying through HTTP is safer because:
- MLflow's workspace store validates names, checks for empty workspaces on delete, manages artifact roots
- Direct store access would require duplicating all that validation
- The HTTP path already has before_request hooks for auth

**Notes:**
- The `ALL_WORKSPACES` endpoint in the frontend (`api-endpoints.ts`) already points to `/api/3.0/mlflow/workspaces` — this fetches from MLflow directly through Flask. The new proxy endpoints at `/oidc/workspaces` would be additional admin-oriented endpoints for CUD operations.
- On create: auto-grant MANAGE permission to the creator in `workspace_permissions` table
- On delete: cascade-delete all `workspace_permissions` and `workspace_group_permissions` rows for that workspace
- On delete: consider which `WorkspaceDeletionMode` to expose (RESTRICT is safest default)

### TS-02: Workspace Management UI (Admin Page)

| Aspect | Detail |
|--------|--------|
| **Why Expected** | Admins need a UI to manage workspace lifecycle, not just member permissions. The current `workspaces-page.tsx` only lists workspaces and links to member management. It lacks create/edit/delete actions. |
| **Complexity** | Medium |
| **Depends On** | TS-01 (workspace CRUD backend) |

**Expected Behavior:**

| Action | UX Pattern | Auth |
|--------|-----------|------|
| Create workspace | "Create Workspace" button → modal/form with name, description fields | Admin only |
| View workspace list | Table with name, description, member count columns | All users (filtered) |
| View workspace detail | Click row → detail page with metadata + member management | Any workspace permission |
| Edit workspace | Edit button → modal/form for description update | Admin only |
| Delete workspace | Delete button → confirmation dialog with safety warning | Admin only, workspace must be empty |

**Workspace Name Validation (Client-Side):**
Must mirror MLflow's `WorkspaceNameValidator`:
- Regex: `^(?!.*--)[a-z0-9]([-a-z0-9]*[a-z0-9])?$`
- Length: 2-63 chars
- Real-time validation feedback in the form
- Reserved name check: `workspaces`, `api`, `ajax-api`, `static-files`

**UI Components Needed:**
- `workspace-create-modal.tsx` — form with name (required), description (optional), default_artifact_root (optional)
- Extend `workspaces-page.tsx` — add Create button, Edit/Delete row actions
- `workspace-edit-modal.tsx` — form for description/artifact_root update (name immutable after creation)
- Delete confirmation component — show warning about RESTRICT mode (workspace must be empty)

**Pattern Consistency:** Follow existing patterns from webhooks management:
- CUD buttons always visible (backend enforces auth, UI shows toast on 403)
- Text input for names, not dropdowns
- Toast notifications for success/error

### TS-03: Global Workspace Picker (UI Header)

| Aspect | Detail |
|--------|--------|
| **Why Expected** | When workspaces are enabled, admins managing permissions need to scope their view to a specific workspace. Without a picker, users see a flat list across all workspaces, which is confusing in multi-tenant setups. |
| **Complexity** | Medium-High |
| **Depends On** | TS-01 (list endpoint), existing workspace list hook (`use-all-workspaces`) |

**Expected Behavior:**

| Aspect | Detail |
|--------|--------|
| **Placement** | Header bar, between logo and navigation links |
| **Visibility** | Only visible when `workspacesEnabled` is `true` in runtime config |
| **Default state** | "All Workspaces" (no filter) or default workspace pre-selected |
| **Selection effect** | Scopes all permission-related pages (experiments, models, prompts, users, groups) to show only resources within the selected workspace |
| **Persistence** | Store selection in React context + localStorage for page refreshes |
| **Admin behavior** | Admins see all workspaces in the picker |
| **Non-admin behavior** | Non-admins see only workspaces they have permission on (already filtered by `_filter_list_workspaces()`) |

**Architecture Decisions:**

1. **React Context for workspace selection** — `WorkspaceContext` provider wrapping the app, with `selectedWorkspace` state
2. **Header integration** — Add `<WorkspacePicker />` component to `header.tsx` between logo and nav links
3. **API integration** — Existing `fetchAllWorkspaces()` service already calls `/api/3.0/mlflow/workspaces`; picker re-uses this data
4. **Downstream effect** — When a workspace is selected, the `X-MLFLOW-WORKSPACE` header should be sent with all API requests from the UI. This means the `http` service (`core/services/http.ts`) needs to read from `WorkspaceContext` and attach the header.
5. **"All Workspaces" mode** — When no workspace is selected, API requests are sent without the header (existing behavior = see everything you have permission for)

**Scoping Behavior per Page:**

| Page | Scoped Behavior |
|------|----------------|
| Experiments | Show only experiments in selected workspace |
| Models | Show only models in selected workspace |
| Prompts | Show only prompts in selected workspace |
| Users | Show user permissions filtered to selected workspace resources |
| Groups | Show group permissions filtered to selected workspace resources |
| Workspaces | Not scoped (always shows all accessible workspaces) |
| AI Gateway | May or may not scope — depends on whether gateway resources are workspace-scoped upstream |

**Implementation Approach:**
- The workspace picker sets `X-MLFLOW-WORKSPACE` header on outgoing requests
- Backend search/list endpoints already filter by workspace when the header is present (MLflow core handles this for experiments/models)
- Permission management pages (FastAPI `/api/2.0/mlflow/permissions/...`) would need to accept workspace context to filter appropriately — this may require updates to some permission listing endpoints

### TS-04: Workspace-Scoped Search Result Filtering

| Aspect | Detail |
|--------|--------|
| **Why Expected** | Currently, `_filter_search_experiments()` and `_filter_search_registered_models()` in `after_request.py` filter by user resource-level permissions only. When workspaces are enabled, they should also consider workspace membership — a user should only see resources in workspaces they belong to. |
| **Complexity** | Medium |
| **Depends On** | Existing after_request filter infrastructure, workspace permission cache (v1.0) |

**Current Filtering (v1.0):**
```
SearchExperiments → _filter_search_experiments() → can_read_experiment(exp_id, username)
SearchRegisteredModels → _filter_search_registered_models() → can_read_registered_model(name, username)
SearchLoggedModels → _filter_search_logged_models() → can_read_experiment(exp_id, username)
ListWorkspaces → _filter_list_workspaces() → get_workspace_permission_cached()
```

**Target Filtering (v1.1):**
The workspace fallback is already in `resolve_permission()` (v1.0), which `can_read_experiment()` and `can_read_registered_model()` ultimately call. So the existing after_request filters should already benefit from workspace-level permissions.

**However**, the gap is in **workspace-scoped filtering** — when `X-MLFLOW-WORKSPACE` header is present, results should be limited to that workspace's resources only. MLflow's tracking store already handles this (experiments/models have `workspace_id` FK), so the search results returned by MLflow should already be workspace-scoped when the header is present.

**The actual gap is**: When workspaces are enabled but no workspace header is sent (e.g., from the SDK without workspace context), the after_request filters need to additionally verify that the user has workspace permission for each experiment/model's workspace. Currently, `can_read_experiment()` checks resource-level permissions with workspace fallback, but doesn't restrict by workspace membership.

**Implementation:**
1. In `_filter_search_experiments()`: After checking `can_read_experiment()`, also check if the experiment's workspace is accessible to the user
2. In `_filter_search_registered_models()`: Same pattern for models
3. This requires knowing which workspace each experiment/model belongs to — which means either:
   - a. Querying MLflow's tracking store for the workspace association (expensive per-item)
   - b. The workspace info is already in the protobuf response (if MLflow includes it)
   - c. Relying on MLflow's built-in workspace filtering when the header is set (simplest)

**Recommended Approach:** Option (c) — rely on MLflow's workspace filtering when header is present. When no header is set and workspaces are enabled, filter the list of workspaces the user has access to, then only include resources from those workspaces. This can use `get_workspace_permission_cached()` which is already fast (TTLCache).

**Edge Cases:**
- Default workspace resources should always be visible if `GRANT_DEFAULT_WORKSPACE_ACCESS` is true
- Admin users bypass all filtering (already handled)
- Resources not assigned to any workspace (pre-workspace-era data) should remain visible

### TS-05: Regex Workspace Permissions

| Aspect | Detail |
|--------|--------|
| **Why Expected** | The plugin already has regex (pattern-based) permissions for experiments, models, prompts, scorers, and all gateway resources. Workspace regex permissions enable bulk access rules like "grant READ to all `team-*` workspaces" — essential for organizations with many workspaces following naming conventions. |
| **Complexity** | Medium |
| **Depends On** | Existing `BaseRegexPermissionRepository` and `BaseGroupRegexPermissionRepository` base classes (v1.0 REFAC-02) |

**Expected Behavior:**

| Feature | Detail |
|---------|--------|
| Regex pattern | Match workspace names against regex (e.g., `^team-.*$`, `^prod-.*$`) |
| Priority | Integer priority for ordering when multiple patterns match |
| User regex | User + regex pattern + priority + permission level |
| Group regex | Group + regex pattern + priority + permission level |
| Resolution order | Direct user → direct group → user regex → group regex (matches existing `PERMISSION_SOURCE_ORDER`) |
| CRUD API | FastAPI endpoints for user regex and group regex workspace permissions |
| Cache interaction | Regex lookups must integrate with or bypass the TTLCache for workspace permissions |

**Data Model (following existing patterns):**

New DB tables:
- `workspace_regex_permissions` — `(id, regex, user_id, permission, priority)` — follows `SqlExperimentRegexPermission` pattern
- `workspace_group_regex_permissions` — `(id, regex, group_id, permission, priority)` — follows `SqlExperimentGroupRegexPermission` pattern

New entities:
- `WorkspaceRegexPermission` — follows `ExperimentRegexPermission` pattern
- `WorkspaceGroupRegexPermission` — follows `ExperimentGroupRegexPermission` pattern

New repositories:
- `WorkspacePermissionRegexRepository` — extends `BaseRegexPermissionRepository`
- `WorkspaceGroupRegexPermissionRepository` — extends `BaseGroupRegexPermissionRepository`

**Cache Integration:**
The existing `_lookup_workspace_permission()` in `workspace_cache.py` checks:
1. Default workspace implicit access
2. Direct user permission
3. Direct group permission

It needs to be extended to also check:
4. User regex permission
5. Group regex permission

This follows the `PERMISSION_SOURCE_ORDER` config pattern (`user → group → regex → group-regex`).

**API Endpoints (following existing patterns):**

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/3.0/mlflow/permissions/users/{username}/workspace-patterns` | GET | List user's workspace regex permissions |
| `/api/3.0/mlflow/permissions/users/{username}/workspace-patterns` | POST | Create user workspace regex permission |
| `/api/3.0/mlflow/permissions/users/{username}/workspace-patterns/{id}` | PATCH | Update user workspace regex permission |
| `/api/3.0/mlflow/permissions/users/{username}/workspace-patterns/{id}` | DELETE | Delete user workspace regex permission |
| `/api/3.0/mlflow/permissions/groups/{group}/workspace-patterns` | GET | List group's workspace regex permissions |
| `/api/3.0/mlflow/permissions/groups/{group}/workspace-patterns` | POST | Create group workspace regex permission |
| `/api/3.0/mlflow/permissions/groups/{group}/workspace-patterns/{id}` | PATCH | Update group workspace regex permission |
| `/api/3.0/mlflow/permissions/groups/{group}/workspace-patterns/{id}` | DELETE | Delete group workspace regex permission |

## Differentiators

Features that enhance the workspace experience beyond table stakes.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Workspace member count in list view** | Show how many users/groups have permissions per workspace | Low | Query workspace permission tables, add to list response |
| **Workspace resource count in list view** | Show experiment/model counts per workspace | Medium | Requires querying MLflow tracking store per workspace — potentially expensive |
| **Workspace picker in sidebar instead of header** | Alternative placement that doesn't crowd the header | Low | Design decision — sidebar has less horizontal space but is always visible |
| **Workspace quick-switch keyboard shortcut** | Power users can switch workspaces with Ctrl+K or similar | Low | Nice UX improvement but not essential |
| **Workspace permission bulk operations** | Assign permissions to multiple users/groups at once | Medium | Currently one-at-a-time in the detail page |
| **Workspace creation from OIDC claim auto-create** | When OIDC login maps to a workspace that doesn't exist, auto-create it | Medium | Depends on admin policy — some orgs want manual workspace provisioning |
| **Workspace deletion cascading to plugin permissions** | When a workspace is deleted upstream, automatically clean up plugin permission tables | Low | after_request hook on DeleteWorkspace to wipe permission rows |

## Anti-Features

Features to explicitly NOT build in v1.1.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Per-workspace artifact store management UI** | Artifact config is MLflow core responsibility; default_artifact_root is set on create and rarely changed | Allow setting on create, omit from edit |
| **Workspace hierarchy / nesting** | MLflow model is flat; nesting adds exponential permission complexity | Use naming conventions (e.g., `org-team-project` pattern) |
| **Cross-workspace resource moving** | Not supported by MLflow — experiments/models are created into a workspace | Document limitation; resource must be recreated in target workspace |
| **Workspace-specific RBAC rules (different permission levels per workspace)** | The permission model is already complex; workspace-scoped permission redefinitions would be unmanageable | Use the existing READ/USE/EDIT/MANAGE levels consistently |
| **Workspace templates** | Pre-configured workspace setups (permissions, artifact roots, etc.) | Manual setup per workspace; can be scripted via API |
| **Workspace usage analytics/dashboard** | Not an auth concern; would require querying MLflow tracking data extensively | Out of scope — use MLflow's built-in UI for usage metrics |
| **Direct workspace store access** | Bypassing MLflow's workspace store for CRUD operations | Always proxy through MLflow's API to preserve validation, deletion constraints, and artifact management |

## Feature Dependencies

```
TS-01: Workspace CRUD Backend
  ├── TS-02: Workspace Management UI (needs CRUD endpoints)
  ├── TS-03: Global Workspace Picker (needs List endpoint)
  └── After-request: Permission cascade on delete (new hook)

TS-02: Workspace Management UI
  └── TS-03: Global Workspace Picker (can share workspace list data)

TS-03: Global Workspace Picker
  ├── TS-04: Workspace-Scoped Search Filtering (picker sets X-MLFLOW-WORKSPACE header)
  └── WorkspaceContext React context (new)

TS-04: Workspace-Scoped Search Filtering
  └── Existing: workspace permission cache (v1.0)
  └── Existing: resolve_permission() workspace fallback (v1.0)

TS-05: Regex Workspace Permissions
  ├── DB Migration (new tables)
  ├── BaseRegexPermissionRepository (existing from REFAC-02)
  ├── BaseGroupRegexPermissionRepository (existing from REFAC-02)
  └── workspace_cache.py update (extend resolution chain)
```

## Implementation Order Recommendation

### Phase 1: Workspace CRUD Backend + Permission Cascade
**TS-01** + delete cascade hook

This is the foundation. Without CRUD proxy endpoints, the UI has nothing to call. The delete cascade ensures permissions are cleaned up when workspaces are removed.

Rationale:
- All other features depend on workspace CRUD being accessible
- The before_request hooks already exist (v1.0) — we just need FastAPI proxy endpoints
- after_request hook for DeleteWorkspace permission cleanup is low-effort and prevents orphaned rows

### Phase 2: Workspace Management UI + Global Picker
**TS-02** + **TS-03**

These can be built together since they share workspace list data and both modify the React app layout.

Rationale:
- The workspace picker needs the workspace list (same data as management page)
- The picker's WorkspaceContext will be used by the management pages too
- Building UI features together avoids duplicate component work

### Phase 3: Workspace-Scoped Search Filtering
**TS-04**

This can be built once the picker exists (so it can set the X-MLFLOW-WORKSPACE header).

Rationale:
- Depends on picker being available to test workspace-scoped behavior
- May be partially handled by MLflow already (when header is present)
- Need to verify edge cases (no header, default workspace, pre-workspace data)

### Phase 4: Regex Workspace Permissions
**TS-05**

This is the most complex feature and benefits from the prior phases being stable.

Rationale:
- Extends existing regex permission infrastructure (well-understood pattern)
- DB migration adds new tables (should be last to minimize migration churn)
- Cache integration requires careful testing against the existing TTLCache
- Lower urgency — direct user/group permissions (v1.0) cover most use cases

## MVP Recommendation

**Must ship (v1.1):**
1. TS-01: Workspace CRUD backend (proxy endpoints)
2. TS-02: Workspace management UI (create/edit/delete)
3. TS-03: Global workspace picker (header dropdown)
4. TS-04: Workspace-scoped search filtering (after_request enhancement)
5. TS-05: Regex workspace permissions (pattern-based access)

**Can defer to v1.2:**
- Workspace member/resource count in list view
- Workspace permission bulk operations
- Workspace creation from OIDC auto-create
- Workspace quick-switch keyboard shortcut

## Sources

- MLflow `WorkspaceNameValidator`: `mlflow.store.workspace.abstract_store.WorkspaceNameValidator` (HIGH confidence — verified from installed 3.10.1 source)
- MLflow `WorkspaceDeletionMode`: `mlflow.store.workspace.abstract_store.WorkspaceDeletionMode` — RESTRICT, SET_DEFAULT, CASCADE enum (HIGH confidence — verified from source)
- MLflow `Workspace` entity: `mlflow.entities.workspace.Workspace` — dataclass with `name`, `description`, `default_artifact_root` (HIGH confidence — verified from source)
- MLflow workspace protobuf fields: `CreateWorkspace(name, description, default_artifact_root)`, `GetWorkspace(workspace_name)`, `UpdateWorkspace(workspace_name, description, default_artifact_root)`, `DeleteWorkspace(workspace_name)`, `ListWorkspaces()` (HIGH confidence — verified via protobuf introspection)
- MLflow workspace endpoints: `GET/POST /api/3.0/mlflow/workspaces`, `GET/PATCH/DELETE /api/3.0/mlflow/workspaces/<workspace_name>` (HIGH confidence — verified via `get_endpoints()`)
- Existing plugin workspace code: `workspace_permissions.py`, `workspace_cache.py`, `validators/workspace.py`, `entities/workspace.py`, `db/models/workspace.py` (HIGH confidence — local source)
- Existing plugin regex infrastructure: `_base.py` (`BaseRegexPermissionRepository`, `BaseGroupRegexPermissionRepository`), 16 regex repositories (HIGH confidence — local source)
- Existing UI components: `workspaces-page.tsx`, `workspace-detail-page.tsx`, `header.tsx`, `sidebar-data.ts`, `api-endpoints.ts` (HIGH confidence — local source)
