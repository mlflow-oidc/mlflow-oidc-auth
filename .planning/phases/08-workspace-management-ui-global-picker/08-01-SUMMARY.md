---
phase: 08-workspace-management-ui-global-picker
plan: 01
subsystem: frontend-workspace-management
tags: [react, workspace, crud, modals, admin-ui, member-counts]
dependency_graph:
  requires: [06-02-PLAN (workspace CRUD backend API)]
  provides: [workspace CRUD modals, workspace service layer, member counts display]
  affects: [workspaces-page, use-all-workspaces hook, entity types, api-endpoints config]
tech_stack:
  added: []
  patterns: [modal CRUD pattern (matching webhook modals), member count aggregation via parallel fetches]
key_files:
  created:
    - web-react/src/features/workspaces/components/create-workspace-modal.tsx
    - web-react/src/features/workspaces/components/create-workspace-modal.test.tsx
    - web-react/src/features/workspaces/components/edit-workspace-modal.tsx
    - web-react/src/features/workspaces/components/edit-workspace-modal.test.tsx
    - web-react/src/features/workspaces/components/delete-workspace-modal.tsx
    - web-react/src/features/workspaces/components/delete-workspace-modal.test.tsx
  modified:
    - web-react/src/shared/types/entity.ts
    - web-react/src/core/configs/api-endpoints.ts
    - web-react/src/core/configs/api-endpoints.test.ts
    - web-react/src/core/services/workspace-service.ts
    - web-react/src/core/services/workspace-service.test.ts
    - web-react/src/core/hooks/use-all-workspaces.ts
    - web-react/src/core/hooks/use-all-workspaces.test.ts
    - web-react/src/features/workspaces/workspaces-page.tsx
    - web-react/src/features/workspaces/workspaces-page.test.tsx
decisions:
  - Followed webhook modal pattern exactly for consistency (Modal + useToast + local isSubmitting state)
  - DNS-safe name validation (2-63 chars, lowercase alphanumeric + hyphens, no leading/trailing hyphens, "default" reserved)
  - Member counts fetched in parallel per-workspace with AbortController for cleanup
  - Delete handled at page level (not modal level) for consistency with webhook pattern
metrics:
  duration: ~5min
  completed: "2026-03-24T20:10:09Z"
  tasks_completed: 3
  tasks_total: 3
  tests_added: 65
  tests_total_passing: 106
---

# Phase 8 Plan 1: Workspace CRUD Management Modals & Member Counts Summary

Admin workspace lifecycle management via modal forms with DNS-safe name validation, member count aggregation via parallel per-workspace API calls, and admin-only CRUD action buttons on the workspaces list page.

## Task Results

### Task 1: Workspace CRUD service layer and API endpoint configuration
**Commit:** `33497ad`
**Status:** Complete

Added workspace CRUD types (`WorkspaceCrudCreateRequest`, `WorkspaceCrudUpdateRequest`, `WorkspaceCrudResponse`, `WorkspaceMemberCounts`) to entity.ts. Added `WORKSPACE_CRUD` static and `WORKSPACE_CRUD_DETAIL` dynamic endpoints. Created `createWorkspace`, `updateWorkspace`, `deleteWorkspace`, and `fetchWorkspaceMemberCounts` service functions following the webhook-service.ts pattern (using `request` from api-utils for mutations). Added comprehensive endpoint and service tests.

**Files:** entity.ts, api-endpoints.ts, api-endpoints.test.ts, workspace-service.ts, workspace-service.test.ts

### Task 2: Create/Edit/Delete workspace modal components with tests
**Commit:** `ee0f370`
**Status:** Complete

Created three modal components following the existing webhook modal pattern:
- **CreateWorkspaceModal**: Real-time DNS-safe name validation (regex `/^[a-z0-9]([a-z0-9-]*[a-z0-9])?$/`, 2-63 chars, "default" reserved), description field, toast feedback
- **EditWorkspaceModal**: Read-only name field, editable description, useEffect sync on workspace prop change
- **DeleteWorkspaceModal**: Safety warning, "default" workspace protection (disables confirm button), "Delete Permanently" danger button

All three include full test coverage: render states, validation cases, service call verification, toast feedback, and edge cases.

**Files:** create-workspace-modal.tsx/.test.tsx, edit-workspace-modal.tsx/.test.tsx, delete-workspace-modal.tsx/.test.tsx

### Task 3: Enhance workspaces page with member counts and admin CRUD actions
**Commit:** `176655b`
**Status:** Complete

Enhanced `useAllWorkspaces` hook to fetch member counts (users + groups) per workspace in parallel with AbortController cleanup. Updated `workspaces-page.tsx` with:
- Members column showing "{N} users, {M} groups" (with "..." loading indicator)
- Admin-only "Create Workspace" button in page header
- Admin-only Edit (pencil) and Delete (trash) IconButtons per row
- Modal integration: CreateWorkspaceModal, EditWorkspaceModal, DeleteWorkspaceModal
- Delete handler with toast feedback and list refresh

Updated tests for admin/non-admin rendering, member counts display, and memberCounts hook behavior.

**Files:** use-all-workspaces.ts/.test.ts, workspaces-page.tsx/.test.tsx

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None - all data sources are wired to real service functions calling backend APIs.

## Verification

Full test suite: 106 tests passing across 9 test files (api-endpoints, workspace-service, 3 modal components, workspaces-page, use-all-workspaces, workspace-detail-page, workspace-members-section).

```
Test Files  9 passed (9)
     Tests  106 passed (106)
```

## Self-Check: PASSED

- All 12 key files verified present on disk
- All 3 task commits verified in git history (33497ad, ee0f370, 176655b)
