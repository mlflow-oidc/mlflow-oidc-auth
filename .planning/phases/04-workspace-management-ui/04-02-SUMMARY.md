---
phase: 04-workspace-management-ui
plan: 02
subsystem: workspace-ui-pages
tags: [workspace, frontend, list-page, detail-page, crud, permissions, react]
dependency_graph:
  requires:
    - workspace-types
    - workspace-api-endpoints
    - workspace-data-hooks
    - workspace-routes
  provides:
    - workspace-list-page
    - workspace-detail-page
    - workspace-members-section
  affects:
    - web-react/src/features/workspaces/workspaces-page.tsx
    - web-react/src/features/workspaces/workspace-detail-page.tsx
    - web-react/src/features/workspaces/components/workspace-members-section.tsx
tech_stack:
  added: []
  patterns:
    - PageContainer/PageStatus/SearchInput/EntityListTable list page pattern
    - WorkspaceMembersSection reusable CRUD table with inline modals
    - request() + DYNAMIC_API_ENDPOINTS for workspace CRUD operations
    - useToast for success/error notifications on all CUD operations
key_files:
  created:
    - web-react/src/features/workspaces/workspaces-page.tsx
    - web-react/src/features/workspaces/workspaces-page.test.tsx
    - web-react/src/features/workspaces/workspace-detail-page.tsx
    - web-react/src/features/workspaces/workspace-detail-page.test.tsx
    - web-react/src/features/workspaces/components/workspace-members-section.tsx
    - web-react/src/features/workspaces/components/workspace-members-section.test.tsx
  modified: []
decisions:
  - "WorkspaceMembersSection uses inline text input for member name (not dropdown Select like GrantPermissionModal) since workspace members are free-form and not pre-loaded from a list"
  - "CUD buttons are always visible to all users per D-14 — backend enforces authorization; UI shows toast on 403 errors"
  - "User CRUD body uses { username, permission } shape; Group CRUD body uses { group_name, permission } shape per plan pitfall 6"
metrics:
  completed_date: "2026-03-23"
  tasks_completed: 2
  tasks_total: 2
  files_created: 6
  files_modified: 0
---

# Phase 04 Plan 02: Workspace Pages & Member Management Summary

**One-liner:** Workspace list page with search/filter and detail page with full CRUD member management (add/edit/remove users and groups with toast notifications).

## What Was Done

### Task 1: Workspace list page with tests

1. **WorkspacesPage** — Replaced placeholder stub with full implementation following `experiments-page.tsx` pattern exactly:
   - Uses `useAllWorkspaces` hook for data fetching
   - Uses `useSearch` hook for client-side search/filter by workspace name
   - Renders `PageContainer` with "Workspaces" title
   - Shows `PageStatus` for loading/error states
   - Displays `SearchInput` and `EntityListTable` with 3 columns:
     - Workspace Name
     - Description (shows "—" for empty descriptions)
     - Members (with "Manage members" `RowActionButton` navigating to `/workspaces/:name`)

2. **workspaces-page.test.tsx** — 8 test cases covering:
   - Loading state
   - Workspace list rendering
   - Search filtering
   - Error state
   - Empty state (no workspaces)
   - Empty search results
   - Null allWorkspaces handling
   - Description column with dash for empty description

### Task 2: Workspace detail page + members section with CRUD and tests

1. **WorkspaceMembersSection** — Reusable component for displaying and managing workspace members (users or groups):
   - Section header with title and member count, plus "Add {title}" button
   - Table with name, permission, and actions columns
   - Edit (pencil icon) and remove (trash icon) action buttons per row
   - Add modal: text input for name + PermissionLevelSelect + Save/Cancel
   - Edit modal: read-only name + PermissionLevelSelect + Save/Cancel
   - Remove: direct delete with toast notification
   - All CUD buttons always visible (per D-14)
   - useToast for success/error notifications
   - Loading/error/empty state handling via PageStatus

2. **workspace-members-section.test.tsx** — 6 test cases covering:
   - Member list rendering with names and permissions
   - Section title with member count
   - Add button visibility
   - Loading state
   - Empty state
   - Edit and remove buttons for each member

3. **WorkspaceDetailPage** — Replaced placeholder stub with full implementation:
   - Gets `workspaceName` from URL params via `useParams`
   - Shows "Workspace name is required." if no param
   - Fetches users via `useWorkspaceUsers` and groups via `useWorkspaceGroups`
   - Renders two `WorkspaceMembersSection` instances (Users + Groups)
   - CRUD handlers use `request()` + `DYNAMIC_API_ENDPOINTS`:
     - User grant: POST to `WORKSPACE_USERS` with `{ username, permission }`
     - User update: PATCH to `WORKSPACE_USER` with `{ username, permission }`
     - User remove: DELETE to `WORKSPACE_USER`
     - Group grant: POST to `WORKSPACE_GROUPS` with `{ group_name, permission }`
     - Group update: PATCH to `WORKSPACE_GROUP` with `{ group_name, permission }`
     - Group remove: DELETE to `WORKSPACE_GROUP`
   - Toast notifications on all CRUD success/error

4. **workspace-detail-page.test.tsx** — 9 test cases covering:
   - Missing workspace param
   - Users and groups sections rendering
   - Workspace name in title
   - User members with permissions
   - Group members with permissions
   - Loading state
   - Empty state (no members)
   - User grant permission (verifies `{ username, permission }` body shape)
   - Group grant permission (verifies `{ group_name, permission }` body shape)

## Deviations from Plan

None — plan executed exactly as written.

## Test Results

### Workspace feature tests
```
Test Files  3 passed (3)
     Tests  23 passed (23)
```

### Full test suite
```
Test Files  109 passed (109)
     Tests  700 passed (700)
```

All 23 new workspace tests pass. Zero regressions in the full suite (700/700).

TypeScript compilation: **clean** (zero errors)

## Known Stubs

None — the Plan 04-01 placeholder stubs have been replaced with full implementations.

## Verification Checklist

- [x] WorkspacesPage renders workspace list with name, description, and manage members columns
- [x] Client-side search filters workspaces by name
- [x] Clicking "Manage members" navigates to workspace detail page
- [x] WorkspaceDetailPage shows Users section with username + permission level table
- [x] WorkspaceDetailPage shows Groups section with group_name + permission level table
- [x] Add User/Group opens modal with name input + permission level select
- [x] Grant sends POST with correct body shape (`username` for users, `group_name` for groups)
- [x] Edit sends PATCH with correct body shape and permission level
- [x] Remove sends DELETE to correct endpoint
- [x] CUD buttons visible to ALL users (not admin-gated) per D-14
- [x] Toast notifications shown for all CRUD operations
- [x] All test files pass with adequate coverage (23/23 workspace tests)
- [x] TypeScript compilation succeeds with no errors
- [x] Full test suite passes with no regressions (700/700)
- [x] Workspace feature module follows project conventions (kebab-case files, PascalCase components)

## Self-Check: PASSED
