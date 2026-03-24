# Phase 4: Workspace Management UI - Context

**Gathered:** 2026-03-23
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase adds a React workspace management feature module to the existing admin UI. After this phase:
- Users see a "Workspaces" link in the sidebar (gated on `workspaces_enabled` feature flag)
- Workspace list page shows all workspaces the current user has access to (via MLflow core ListWorkspaces API)
- Workspace detail page shows members (users + groups) with their permission levels
- Admin and workspace MANAGE users can add/edit/remove workspace members via the UI
- Backend config.json endpoint exposes `workspaces_enabled` flag for frontend consumption

**Requirements:** WSMGMT-04, WSMGMT-05, WSMGMT-06
**Backend dependency:** Phase 3 workspace permission CRUD API (8 endpoints at `/api/3.0/mlflow/permissions/workspaces`)

</domain>

<decisions>
## Implementation Decisions

### Feature Module Structure (WSMGMT-04)
- **D-01:** New `src/features/workspaces/` feature module following existing experiments/groups pattern. Contains `workspaces-page.tsx` (list), `workspace-detail-page.tsx` (detail/members), and `components/` subdirectory for workspace-specific components.
- **D-02:** Co-located test files (`*.test.tsx`) following existing convention — no separate `__tests__` directories.

### Routing (WSMGMT-04, WSMGMT-05)
- **D-03:** Two new routes: `/workspaces` (list page) and `/workspaces/:workspaceName` (detail page). Both wrapped in `ProtectedLayoutRoute` following existing pattern in `app.tsx`.
- **D-04:** Lazy-loaded route components via `React.lazy()` following existing pattern for all feature pages.

### Workspace List Page (WSMGMT-04)
- **D-05:** Workspace list fetched from MLflow core's `/api/3.0/mlflow/workspaces` (GET). Response shape is `{ workspaces: [{ name, description, default_artifact_root }] }` — hook must unwrap the `workspaces` array.
- **D-06:** List page uses `EntityListTable` + `ColumnConfig<T>` pattern (from experiments-page.tsx). Columns: workspace name (clickable link to detail), description, "Manage members" action button.
- **D-07:** Search/filter via existing `useSearch` + `SearchInput` pattern — client-side filtering by workspace name.

### Workspace Detail Page (WSMGMT-04, WSMGMT-06)
- **D-08:** Detail page displays two sections: Users and Groups. Each shows a table of members with their permission level and action buttons (edit permission, remove).
- **D-09:** "Add user" and "Add group" buttons open modal dialogs following existing `GrantPermissionModal` pattern for granting workspace permissions.
- **D-10:** Permission level selection uses existing `PermissionLevelSelect` component — same 5 levels (READ, USE, EDIT, MANAGE, NO_PERMISSIONS).

### Workspace Switcher / Navigation (WSMGMT-05)
- **D-11:** Workspace switcher implemented as a sidebar navigation link to `/workspaces` (not a global workspace context switcher). Gated on `workspaces_enabled` from RuntimeConfig. Uses `faBuilding` or `faLayerGroup` FontAwesome icon.
- **D-12:** No global workspace context state — users navigate to workspace list, then click through to manage individual workspaces. A global context switcher would require `X-MLFLOW-WORKSPACE` header propagation in all API calls, which is out of scope.

### Member Management Access (WSMGMT-06)
- **D-13:** CUD controls (add/edit/remove member buttons) visible to both admin users AND users with MANAGE permission on the workspace. Backend already enforces authorization via `check_workspace_manage_permission` dependency — UI should not be more restrictive than the API.
- **D-14:** Simplest approach: always show CUD buttons on workspace detail page and let the backend reject unauthorized requests with proper error handling (toast notification on 403).

### API Integration
- **D-15:** Workspace API endpoints added to `api-endpoints.ts`. Note: workspace APIs use v3.0 prefix (`/api/3.0/`), not v2.0 like existing endpoints. This is the first v3.0 integration in the frontend.
- **D-16:** Service layer functions in `core/services/workspace-service.ts` using `createStaticApiFetcher` and `createDynamicApiFetcher` patterns.
- **D-17:** Data hooks in `core/hooks/`: `use-all-workspaces.ts`, `use-workspace-users.ts`, `use-workspace-groups.ts` following `useApi<T>` pattern.
- **D-18:** CRUD operations follow `use-permissions-management.ts` pattern using `request()` from `api-utils.ts` directly — no workspace-specific CRUD abstraction layer.

### Backend Config Change
- **D-19:** Backend `serve_spa_config` in `mlflow_oidc_auth/routers/ui.py` must add `"workspaces_enabled": config.MLFLOW_ENABLE_WORKSPACES` to the config.json response.
- **D-20:** Frontend `RuntimeConfig` type in `runtime-config.ts` must add `workspaces_enabled: boolean` field.
- **D-21:** `getSidebarData` function signature updated to accept `workspacesEnabled` parameter. All callers (sidebar.tsx, sidebar-data.test.ts) updated.

### Agent's Discretion
- Exact column layout and spacing in workspace list/detail tables
- Modal form field layout and validation messages
- Whether workspace detail page uses tabs for users/groups or side-by-side sections
- Toast notification messages for CRUD operations
- Loading/error state presentation details
- Whether to add workspace-specific TypeScript types in a `features/workspaces/types/` directory or in `shared/types/entity.ts`

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Feature Module Pattern
- `web-react/src/features/experiments/experiments-page.tsx` — Reference list page pattern (search, table, columns, loading)
- `web-react/src/features/experiments/experiments-page.test.tsx` — Reference list page test pattern
- `web-react/src/features/experiments/experiment-permissions-page.tsx` — Reference detail/permissions page pattern
- `web-react/src/features/groups/group-permissions-page.tsx` — Alternative permissions page pattern

### Shared Components
- `web-react/src/shared/components/page/page-container.tsx` — Page layout wrapper
- `web-react/src/shared/components/page/page-status.tsx` — Loading/error states
- `web-react/src/shared/components/entity/entity-list-table.tsx` — Generic list table with ColumnConfig
- `web-react/src/shared/components/search/search-input.tsx` — Search bar
- `web-react/src/shared/components/permissions/grant-permission-modal.tsx` — Permission grant modal
- `web-react/src/shared/components/permissions/permission-level-select.tsx` — Permission dropdown

### Navigation & Routing
- `web-react/src/shared/components/sidebar/sidebar-data.ts` — Sidebar navigation data (add workspace link)
- `web-react/src/shared/components/sidebar/sidebar.tsx` — Sidebar component (caller of getSidebarData)
- `web-react/src/app.tsx` — Route registration (add workspace routes)

### API Layer
- `web-react/src/core/configs/api-endpoints.ts` — Endpoint constants (add workspace endpoints)
- `web-react/src/core/services/entity-service.ts` — Service fetcher pattern (createStaticApiFetcher, createDynamicApiFetcher)
- `web-react/src/core/services/api-utils.ts` — Request utility for CRUD operations
- `web-react/src/core/hooks/use-api.ts` — Data fetching hook pattern
- `web-react/src/core/hooks/use-all-experiments.ts` — Reference data hook pattern

### Configuration
- `web-react/src/shared/services/runtime-config.ts` — RuntimeConfig type (add workspaces_enabled)
- `mlflow_oidc_auth/routers/ui.py` — Backend config.json endpoint (add workspaces_enabled)

### Types
- `web-react/src/shared/types/entity.ts` — Entity type definitions (add workspace types)

### Permissions Pattern
- `web-react/src/features/permissions/hooks/use-permissions-management.ts` — CRUD operations pattern

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `EntityListTable` + `ColumnConfig<T>` — Generic table for list pages, handles search highlighting and empty states
- `GrantPermissionModal` — Modal for granting permissions with username/group input and permission level select
- `PermissionLevelSelect` — Dropdown for selecting READ/USE/EDIT/MANAGE/NO_PERMISSIONS
- `PageContainer` + `PageStatus` — Standard page layout with loading/error states
- `useSearch` + `SearchInput` — Client-side search with submit/clear
- `useApi<T>` — Generic data fetching hook with loading/error/abort handling
- `createStaticApiFetcher` / `createDynamicApiFetcher` — Service layer factory functions
- `request()` from `api-utils.ts` — Low-level authenticated request function for CRUD
- `useToast()` — Toast notifications for success/error feedback
- `useRuntimeConfig()` — Runtime configuration access via React Context

### Established Patterns
- Feature modules at `src/features/<name>/` with pages, components, hooks subdirectories
- Lazy-loaded routes via `React.lazy()` in `app.tsx`
- `ProtectedLayoutRoute` wraps all authenticated routes
- Sidebar data function returns NavLinkData array, conditionally includes items based on feature flags
- API endpoints split into STATIC (no params) and DYNAMIC (parameterized) endpoint maps
- Data hooks wrap `useApi<T>` with service fetcher, provide named return values
- CRUD operations use `request()` directly with method/body, followed by toast + refetch

### Integration Points
- `web-react/src/app.tsx` — Register 2 new lazy routes
- `web-react/src/core/configs/api-endpoints.ts` — Add 5 endpoint constants (1 static, 4 dynamic)
- `web-react/src/shared/services/runtime-config.ts` — Add `workspaces_enabled` to RuntimeConfig type
- `web-react/src/shared/components/sidebar/sidebar-data.ts` — Add workspace sidebar link
- `web-react/src/shared/types/entity.ts` — Add workspace type definitions
- `mlflow_oidc_auth/routers/ui.py` — Add `workspaces_enabled` to config.json response

</code_context>

<specifics>
## Specific Ideas

### Workspace List Page Layout
The workspace list page should closely mirror experiments-page.tsx: title "Workspaces", search bar, table with workspace name (as link to detail), description, and "Manage members" action button. No create/delete workspace functionality in UI (workspace lifecycle managed via MLflow API directly).

### Workspace Detail Page Layout
Two-section layout showing Users and Groups tables. Each table shows member name and permission level with edit/delete action buttons. "Add User" and "Add Group" buttons at the top of each section open modal dialogs. Section headers show count of members.

### API Version Consideration
All existing frontend endpoints use `/api/2.0/`. Workspace endpoints are the first `/api/3.0/` endpoints. The endpoint constants must use the correct v3.0 prefix. This affects `api-endpoints.ts` only — the `request()` function doesn't assume any prefix.

### Response Shape Difference
MLflow core `ListWorkspaces` returns `{ workspaces: [{ name, description, default_artifact_root }] }`. The `useAllWorkspaces` hook must unwrap the `workspaces` array from the response — different from existing hooks which receive flat arrays.

</specifics>

<deferred>
## Deferred Ideas

- **Global workspace context switcher** — A header dropdown that sets active workspace across all views, requiring X-MLFLOW-WORKSPACE header in all API calls. Much larger scope, deferred to future iteration.
- **Workspace creation/deletion UI** — Workspace lifecycle management (create, update, delete) via the admin UI. Currently managed through MLflow core API directly.
- **Workspace-scoped experiment/model views** — Filtering experiments and models by workspace in the existing list views. Would require workspace context state propagation.
- **Workspace permission level indicators** — Showing the current user's permission level for each workspace in the list view. Would require additional API call or response enrichment.

</deferred>

---

*Phase: 04-workspace-management-ui*
*Context gathered: 2026-03-23*
