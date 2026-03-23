---
phase: 04-workspace-management-ui
plan: 01
subsystem: workspace-ui-infrastructure
tags: [workspace, frontend, backend-config, hooks, service-layer, sidebar, routes]
dependency_graph:
  requires: []
  provides:
    - workspace-runtime-config
    - workspace-types
    - workspace-api-endpoints
    - workspace-service-fetchers
    - workspace-data-hooks
    - workspace-sidebar-navigation
    - workspace-routes
  affects:
    - mlflow_oidc_auth/routers/ui.py
    - web-react/src/shared/services/runtime-config.ts
    - web-react/src/shared/types/entity.ts
    - web-react/src/core/configs/api-endpoints.ts
    - web-react/src/shared/components/sidebar-data.ts
    - web-react/src/shared/components/sidebar.tsx
    - web-react/src/app.tsx
tech_stack:
  added: []
  patterns:
    - createStaticApiFetcher/createDynamicApiFetcher for workspace endpoints
    - useApi hook wrapper pattern for workspace data hooks
    - Conditional sidebar link pattern gated on runtime config
key_files:
  created:
    - web-react/src/core/services/workspace-service.ts
    - web-react/src/core/services/workspace-service.test.ts
    - web-react/src/core/hooks/use-all-workspaces.ts
    - web-react/src/core/hooks/use-all-workspaces.test.ts
    - web-react/src/core/hooks/use-workspace-users.ts
    - web-react/src/core/hooks/use-workspace-users.test.ts
    - web-react/src/core/hooks/use-workspace-groups.ts
    - web-react/src/core/hooks/use-workspace-groups.test.ts
    - web-react/src/features/workspaces/workspaces-page.tsx
    - web-react/src/features/workspaces/workspace-detail-page.tsx
  modified:
    - mlflow_oidc_auth/routers/ui.py
    - web-react/src/shared/services/runtime-config.ts
    - web-react/src/shared/types/entity.ts
    - web-react/src/core/configs/api-endpoints.ts
    - web-react/src/shared/components/sidebar-data.ts
    - web-react/src/shared/components/sidebar-data.test.ts
    - web-react/src/shared/components/sidebar.tsx
    - web-react/src/shared/components/sidebar.test.tsx
    - web-react/src/app.tsx
decisions:
  - Placeholder page stubs created for workspaces-page.tsx and workspace-detail-page.tsx to prevent test failures from lazy imports (Plan 04-02 will replace with full implementations)
metrics:
  completed_date: "2026-03-23"
  tasks_completed: 2
  tasks_total: 2
  files_created: 10
  files_modified: 9
---

# Phase 04 Plan 01: Workspace UI Infrastructure Summary

**One-liner:** Complete workspace UI data pipeline from backend config.json through TypeScript types, API endpoints, service fetchers, data hooks, sidebar navigation, and route registration.

## What Was Done

### Task 1: Backend config + types + API endpoints + service layer + hooks

1. **Backend config.json** — Added `workspaces_enabled: config.MLFLOW_ENABLE_WORKSPACES` to the `/config.json` endpoint response in `mlflow_oidc_auth/routers/ui.py`

2. **RuntimeConfig type** — Added `workspaces_enabled: boolean` field to the `RuntimeConfig` TypeScript type

3. **Workspace TypeScript types** — Added 4 new types to `entity.ts`:
   - `WorkspaceListItem` (name, description, default_artifact_root)
   - `WorkspaceListResponse` (wraps `workspaces: WorkspaceListItem[]`)
   - `WorkspaceUserPermission` (workspace, username, permission)
   - `WorkspaceGroupPermission` (workspace, group_name, permission)

4. **API endpoint constants** — Added 5 workspace endpoint constants:
   - 1 static: `ALL_WORKSPACES` → `/api/3.0/mlflow/workspaces`
   - 4 dynamic: `WORKSPACE_USERS`, `WORKSPACE_GROUPS`, `WORKSPACE_USER`, `WORKSPACE_GROUP` → all using `/api/3.0/` prefix

5. **Service layer** — Created `workspace-service.ts` with 3 fetcher functions:
   - `fetchAllWorkspaces` (static, returns `WorkspaceListResponse`)
   - `fetchWorkspaceUsers` (dynamic, returns `WorkspaceUserPermission[]`)
   - `fetchWorkspaceGroups` (dynamic, returns `WorkspaceGroupPermission[]`)

6. **Data hooks** — Created 3 hooks:
   - `useAllWorkspaces` — unwraps `data.workspaces` from response envelope
   - `useWorkspaceUsers` — returns empty array when workspace is undefined
   - `useWorkspaceGroups` — same guard pattern as useWorkspaceUsers

7. **Tests** — Created 4 test files (12 test cases):
   - `workspace-service.test.ts` (3 tests)
   - `use-all-workspaces.test.ts` (3 tests)
   - `use-workspace-users.test.ts` (3 tests)
   - `use-workspace-groups.test.ts` (3 tests)

### Task 2: Sidebar navigation + route registration

1. **getSidebarData** — Updated signature to accept 3 params `(isAdmin, genAiGatewayEnabled, workspacesEnabled)`, added conditional Workspaces link with `faBuilding` icon between AI Gateway and admin sections

2. **Sidebar component** — Updated to destructure `workspaces_enabled` from RuntimeConfig, pass to getSidebarData, and handle `isWorkspaceStart` divider logic alongside existing AI and admin dividers

3. **sidebar-data.test.ts** — Updated all existing tests for 3-param signature, added 2 new tests:
   - Workspaces link when enabled (7 items)
   - All links when everything enabled (12 items)

4. **sidebar.test.tsx** — Updated mock to accept 3 params, added `workspaces_enabled` to mockRuntimeConfig, added 2 new tests:
   - Renders Workspaces link when enabled
   - Hides Workspaces link when disabled

5. **app.tsx** — Added 2 lazy-loaded workspace routes:
   - `/workspaces` → `WorkspacesPage`
   - `/workspaces/:workspaceName` → `WorkspaceDetailPage`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Created placeholder page stubs for workspace routes**
- **Found during:** Task 2, route registration
- **Issue:** Lazy imports in app.tsx reference `./features/workspaces/workspaces-page` and `./features/workspaces/workspace-detail-page` which don't exist yet (Plan 04-02 will create them). This caused `app.test.tsx` and `main.test.tsx` to fail with "Failed to resolve import" errors (2 test suites, blocking full test suite).
- **Fix:** Created minimal placeholder components (`workspaces-page.tsx` and `workspace-detail-page.tsx`) that render basic divs. These will be replaced with full implementations in Plan 04-02.
- **Files created:** `web-react/src/features/workspaces/workspaces-page.tsx`, `web-react/src/features/workspaces/workspace-detail-page.tsx`

## Test Results

```
Test Files  106 passed (106)
     Tests  677 passed (677)
```

All 25 new/updated tests pass. Zero regressions in the full suite.

TypeScript compilation: **clean** (zero errors)

Python syntax check: **OK**

## Known Stubs

| File | Line | Reason |
|------|------|--------|
| `web-react/src/features/workspaces/workspaces-page.tsx` | 3 | Placeholder — Plan 04-02 will implement full page |
| `web-react/src/features/workspaces/workspace-detail-page.tsx` | 3 | Placeholder — Plan 04-02 will implement full page |

These stubs are intentional scaffolding that do NOT prevent this plan's goal (UI infrastructure wiring) from being achieved. Plan 04-02 is explicitly scoped to replace them with full workspace page implementations.

## Verification Checklist

- [x] Backend config.json includes `workspaces_enabled` field sourced from `config.MLFLOW_ENABLE_WORKSPACES`
- [x] `RuntimeConfig` type has `workspaces_enabled: boolean` field
- [x] 4 workspace types exported from entity.ts
- [x] 5 workspace API endpoint constants (1 static, 4 dynamic) all using `/api/3.0/` prefix
- [x] 3 service fetcher functions work with correct endpoint keys
- [x] 3 data hooks follow existing patterns
- [x] useAllWorkspaces correctly unwraps the `{ workspaces: [...] }` response envelope
- [x] Sidebar shows "Workspaces" link conditionally based on `workspaces_enabled` config flag
- [x] 2 workspace routes registered in app.tsx as lazy-loaded ProtectedLayoutRoutes
- [x] All new and updated tests pass (25/25)
- [x] TypeScript compilation succeeds with no errors
- [x] Full test suite passes with no regressions (677/677)
