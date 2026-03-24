---
phase: 08-workspace-management-ui-global-picker
verified: 2026-03-24T20:45:00Z
status: passed
score: 5/5 must-haves verified
gaps: []
human_verification:
  - test: "Open workspace picker, select a workspace, navigate between pages"
    expected: "Picker persists selection, all API calls include X-MLFLOW-WORKSPACE header in network tab"
    why_human: "Requires running application with real browser and network inspector"
  - test: "Admin creates workspace with DNS-invalid name, then valid name"
    expected: "Real-time validation error appears instantly, valid name submits successfully"
    why_human: "UX responsiveness and visual validation cannot be verified programmatically"
  - test: "Press Ctrl+K (or Cmd+K on Mac) to open workspace picker"
    expected: "Picker opens immediately with search input focused"
    why_human: "Keyboard shortcut interaction in real browser context"
---

# Phase 8: Workspace Management UI & Global Picker Verification Report

**Phase Goal:** Admins can manage workspace lifecycle through the UI, and all users can scope their view to a specific workspace via a header dropdown
**Verified:** 2026-03-24T20:45:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Admin can create, edit, and delete workspaces via modal forms with real-time name validation and confirmation dialogs | ✓ VERIFIED | `create-workspace-modal.tsx` has DNS-safe regex `/^[a-z0-9]([a-z0-9-]*[a-z0-9])?$/`, 2-63 char validation, reserved "default" check. `edit-workspace-modal.tsx` has read-only name + editable description. `delete-workspace-modal.tsx` has safety warning + "default" protection + "Delete Permanently" danger button. All wired to workspace-service.ts CRUD functions. |
| 2 | Workspace list page shows member count (users + groups) per workspace, and admin can bulk-assign permissions | ✓ VERIFIED | `workspaces-page.tsx` renders Members column with `{memberCounts?.[item.name]?.users ?? "…"} users, {memberCounts?.[item.name]?.groups ?? "…"} groups`. `use-all-workspaces.ts` fetches member counts in parallel. `bulk-assign-modal.tsx` accepts comma/newline-separated names, calls `onGrant` sequentially, shows result summary. Integrated in `workspace-detail-page.tsx` with admin-only "Bulk Assign Users" and "Bulk Assign Groups" buttons. |
| 3 | Header dropdown shows accessible workspaces, selecting one sends X-MLFLOW-WORKSPACE header on all subsequent API requests | ✓ VERIFIED | `workspace-picker.tsx` renders in `header.tsx` between logo and controls. Uses `useWorkspace()` context + `useAllWorkspaces()` hook. `http.ts` imports `getActiveWorkspace` and conditionally adds `X-MLFLOW-WORKSPACE` header. Returns null when `config.workspaces_enabled` is false. |
| 4 | Workspace selection persists across page refreshes, "All Workspaces" option removes scoping | ✓ VERIFIED | `workspace-context.tsx` reads from `localStorage.getItem("mlflow-oidc-workspace")` on init, syncs via `useEffect`. `setSelectedWorkspace(null)` removes from localStorage and module-level state. `http.ts` sends no header when `getActiveWorkspace()` returns null. "All Workspaces" in picker calls `handleSelect(null)`. |
| 5 | Picker includes search/filter for many-workspace deployments and keyboard shortcut for quick switching | ✓ VERIFIED | `workspace-picker.tsx` has filter input with `useMemo` filtering by `ws.name.toLowerCase().includes(filter.toLowerCase())`. Keyboard shortcut `(e.metaKey || e.ctrlKey) && e.key === "k"` toggles dropdown. `<kbd>` badge shows `⌘K` or `Ctrl+K` based on platform detection. Escape closes dropdown. Click-outside closes dropdown. |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `web-react/src/features/workspaces/components/create-workspace-modal.tsx` | Create workspace modal with DNS name validation | ✓ VERIFIED | 111 lines, exports `CreateWorkspaceModal` + `validateWorkspaceName`, DNS regex, 2-63 chars, reserved "default" |
| `web-react/src/features/workspaces/components/edit-workspace-modal.tsx` | Edit workspace description modal | ✓ VERIFIED | 80 lines, exports `EditWorkspaceModal`, read-only name, editable description, useEffect sync |
| `web-react/src/features/workspaces/components/delete-workspace-modal.tsx` | Delete workspace confirmation dialog | ✓ VERIFIED | 57 lines, exports `DeleteWorkspaceModal`, safety warning, "default" protection, danger button |
| `web-react/src/features/workspaces/workspaces-page.tsx` | Enhanced workspace list with member counts + admin CRUD | ✓ VERIFIED | 186 lines, imports all 3 modals, useUser for admin check, member count column, admin-only Create/Edit/Delete buttons |
| `web-react/src/shared/components/workspace-picker.tsx` | Dropdown with search, keyboard shortcut, workspace list | ✓ VERIFIED | 144 lines, exports `WorkspacePicker`, search filter, Ctrl+K/Cmd+K, click-outside, Escape, platform detection |
| `web-react/src/shared/context/workspace-context.tsx` | WorkspaceProvider with localStorage persistence | ✓ VERIFIED | 56 lines, exports `WorkspaceProvider`, `getActiveWorkspace`, `setActiveWorkspace`, localStorage sync |
| `web-react/src/shared/context/use-workspace.ts` | Hook to read/set selected workspace | ✓ VERIFIED | 18 lines, exports `useWorkspace`, `WorkspaceContext`, throws outside provider |
| `web-react/src/core/services/http.ts` | HTTP client with X-MLFLOW-WORKSPACE header injection | ✓ VERIFIED | 44 lines, imports `getActiveWorkspace`, conditionally adds header |
| `web-react/src/shared/components/header.tsx` | Header with WorkspacePicker rendered | ✓ VERIFIED | 76 lines, imports and renders `<WorkspacePicker />` between logo and controls |
| `web-react/src/core/services/workspace-service.ts` | CRUD mutation functions | ✓ VERIFIED | 85 lines, exports `createWorkspace`, `updateWorkspace`, `deleteWorkspace`, `fetchWorkspaceMemberCounts` |
| `web-react/src/features/workspaces/components/bulk-assign-modal.tsx` | Bulk permission assignment modal | ✓ VERIFIED | 115 lines, exports `BulkAssignModal`, textarea input, comma/newline parsing, sequential grants, result summary |
| `web-react/src/features/workspaces/workspace-detail-page.tsx` | Detail page with bulk assign buttons for admins | ✓ VERIFIED | 192 lines, imports `useUser` + `BulkAssignModal`, admin-only bulk assign buttons, two modal instances |
| `web-react/src/main.tsx` | Provider tree with WorkspaceProvider | ✓ VERIFIED | WorkspaceProvider wraps between UserProvider and ToastProvider |
| `web-react/src/core/hooks/use-all-workspaces.ts` | Hook with memberCounts | ✓ VERIFIED | 55 lines, fetches member counts per-workspace in parallel with AbortController |
| `web-react/src/core/configs/api-endpoints.ts` | WORKSPACE_CRUD + WORKSPACE_CRUD_DETAIL endpoints | ✓ VERIFIED | Static `WORKSPACE_CRUD: "/api/3.0/mlflow/workspaces/crud"` + Dynamic `WORKSPACE_CRUD_DETAIL` with encodeURIComponent |
| `web-react/src/shared/types/entity.ts` | CRUD types | ✓ VERIFIED | `WorkspaceCrudCreateRequest`, `WorkspaceCrudUpdateRequest`, `WorkspaceCrudResponse`, `WorkspaceMemberCounts` all present |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `create-workspace-modal.tsx` | `workspace-service.ts` | `createWorkspace()` call | ✓ WIRED | Line 6: `import { createWorkspace }`, Line 58: `await createWorkspace({...})` |
| `workspaces-page.tsx` | `workspace-service.ts` | `fetchWorkspaceMemberCounts` via hook | ✓ WIRED | `useAllWorkspaces()` returns `memberCounts`, hook imports `fetchWorkspaceMemberCounts` |
| `workspace-service.ts` | `api-endpoints.ts` | `WORKSPACE_CRUD` endpoint keys | ✓ WIRED | Lines 46, 59, 69 use `STATIC_API_ENDPOINTS.WORKSPACE_CRUD` and `DYNAMIC_API_ENDPOINTS.WORKSPACE_CRUD_DETAIL` |
| `workspace-picker.tsx` | `use-workspace.ts` | `useWorkspace()` hook | ✓ WIRED | Line 2: `import { useWorkspace }`, Line 10: `const { selectedWorkspace, setSelectedWorkspace } = useWorkspace()` |
| `http.ts` | `workspace-context.tsx` | `getActiveWorkspace()` getter | ✓ WIRED | Line 1: `import { getActiveWorkspace }`, Line 21: `const workspace = getActiveWorkspace()` |
| `header.tsx` | `workspace-picker.tsx` | `WorkspacePicker` rendered in header | ✓ WIRED | Line 8: `import { WorkspacePicker }`, Line 45: `<WorkspacePicker />` |
| `main.tsx` | `workspace-context.tsx` | `WorkspaceProvider` in provider tree | ✓ WIRED | Line 12: `import { WorkspaceProvider }`, Line 28-30: wraps between UserProvider and ToastProvider |
| `bulk-assign-modal.tsx` | `workspace-detail-page.tsx` | `onGrant` callback prop | ✓ WIRED | Detail page passes `handleGrantUser`/`handleGrantGroup` as `onGrant` props to `BulkAssignModal` instances |
| `workspace-detail-page.tsx` | `use-user.ts` | `useUser()` for admin check | ✓ WIRED | Line 5: `import { useUser }`, Line 18-19: `const { currentUser } = useUser(); const isAdmin = currentUser?.is_admin ?? false;` |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `workspace-picker.tsx` | `allWorkspaces` | `useAllWorkspaces()` → `fetchAllWorkspaces` → API `/api/3.0/mlflow/workspaces` | Yes — fetches from real API endpoint | ✓ FLOWING |
| `workspace-picker.tsx` | `selectedWorkspace` | `useWorkspace()` → `WorkspaceProvider` state (localStorage init) | Yes — state from context, persisted | ✓ FLOWING |
| `workspaces-page.tsx` | `memberCounts` | `useAllWorkspaces()` → `fetchWorkspaceMemberCounts` → parallel API calls | Yes — fetches users/groups counts from real endpoints | ✓ FLOWING |
| `http.ts` | `workspace` header | `getActiveWorkspace()` → module-level `_activeWorkspace` synced by `WorkspaceProvider` | Yes — synced from React context state | ✓ FLOWING |
| `bulk-assign-modal.tsx` | grant results | `onGrant` prop → `handleGrantUser`/`handleGrantGroup` → `request()` → real API POST | Yes — calls real workspace permission API | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Frontend tests pass | `cd web-react && yarn vitest run` | 116 test files, 792 tests passed | ✓ PASS |
| Backend tests pass | `python -m pytest mlflow_oidc_auth/tests/ -q --ignore=...test_ui.py` | 2407 passed, 0 failed | ✓ PASS |
| All 7 phase commits exist | `git log --oneline --no-walk <hashes>` | All 7 commits verified | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| WSUI-01 | 08-01-PLAN | Admin can create workspace via modal with real-time name validation | ✓ SATISFIED | `create-workspace-modal.tsx` with DNS-safe validation, `createWorkspace` service call |
| WSUI-02 | 08-01-PLAN | Admin can edit workspace description via modal form | ✓ SATISFIED | `edit-workspace-modal.tsx` with read-only name, editable description, `updateWorkspace` service call |
| WSUI-03 | 08-01-PLAN | Admin can delete workspace via confirmation dialog with safety warning | ✓ SATISFIED | `delete-workspace-modal.tsx` with safety warning, "default" protection, danger button |
| WSUI-04 | 08-01-PLAN | Workspace list shows member count per workspace | ✓ SATISFIED | `workspaces-page.tsx` renders `{N} users, {M} groups` per row via `useAllWorkspaces().memberCounts` |
| WSUI-05 | 08-03-PLAN | Admin can bulk-assign permissions to multiple users/groups | ✓ SATISFIED | `bulk-assign-modal.tsx` with comma/newline parsing, `workspace-detail-page.tsx` with admin-only buttons |
| WSPICK-01 | 08-02-PLAN | Header dropdown shows workspaces when enabled | ✓ SATISFIED | `workspace-picker.tsx` returns null when `!config.workspaces_enabled`, renders dropdown otherwise |
| WSPICK-02 | 08-02-PLAN | Selecting workspace sends X-MLFLOW-WORKSPACE header | ✓ SATISFIED | `http.ts` reads `getActiveWorkspace()`, adds header when non-null |
| WSPICK-03 | 08-02-PLAN | Selection persists via localStorage | ✓ SATISFIED | `workspace-context.tsx` uses `localStorage.getItem/setItem("mlflow-oidc-workspace")` |
| WSPICK-04 | 08-02-PLAN | "All Workspaces" removes scoping | ✓ SATISFIED | `handleSelect(null)` → removes from localStorage → `getActiveWorkspace()` returns null → no header |
| WSPICK-05 | 08-02-PLAN | Picker includes search/filter | ✓ SATISFIED | `workspace-picker.tsx` has filter input + `useMemo` case-insensitive filtering |
| WSPICK-06 | 08-02-PLAN | Keyboard shortcut for quick switching | ✓ SATISFIED | `workspace-picker.tsx` handles `(e.metaKey \|\| e.ctrlKey) && e.key === "k"` with platform detection |

**Orphaned requirements:** None. All 11 phase requirements (WSUI-01 through WSUI-05, WSPICK-01 through WSPICK-06) are claimed by plans and satisfied.

**REQUIREMENTS.md status check:** WSUI-01 through WSUI-04 are marked `[ ]` (Pending) in REQUIREMENTS.md but implementation is complete. WSUI-05 and WSPICK-01 through WSPICK-06 are correctly marked `[x]` (Complete). The 4 unchecked boxes are a documentation lag, not a code gap.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None | — | — | — | No anti-patterns found |

No TODO/FIXME/HACK/placeholder markers. No empty implementations. All `return null` occurrences are legitimate null guards (workspace prop is null) or validation returns. No hardcoded empty data in rendering paths.

### Human Verification Required

### 1. Workspace Picker End-to-End Flow

**Test:** Open the app, click the workspace picker, select a workspace, navigate between pages
**Expected:** Picker shows accessible workspaces, selection persists, all API calls include `X-MLFLOW-WORKSPACE` header visible in browser network tab. Refreshing page preserves selection.
**Why human:** Requires running application with real browser and network inspector

### 2. DNS Name Validation UX

**Test:** Admin opens create workspace modal, types invalid names (e.g., "AB", "a-", "-a", "default")
**Expected:** Real-time error messages appear as user types, submit button stays disabled for invalid names
**Why human:** UX responsiveness and visual validation timing

### 3. Keyboard Shortcut

**Test:** Press Ctrl+K (Windows/Linux) or Cmd+K (Mac) on any page
**Expected:** Workspace picker opens immediately with search input focused, typing filters the list
**Why human:** Keyboard shortcut interaction in real browser context

### 4. Bulk Assign Partial Failure

**Test:** Admin opens bulk assign, enters mix of valid and invalid usernames, submits
**Expected:** Modal stays open showing "✓ N assigned, ✗ M failed: names" summary, valid users granted
**Why human:** Requires real API interaction to test partial failure path

### Gaps Summary

No gaps found. All 5 success criteria are verified. All 11 requirements are satisfied by implementation. All 16 artifacts exist, are substantive, and properly wired. All key links verified. Data flows through from API to rendering. All 792 frontend tests and 2407 backend tests pass.

The only documentation lag is that WSUI-01 through WSUI-04 in REQUIREMENTS.md are still marked `[ ]` (Pending) while implementation is complete. This is a doc update issue, not a code gap.

---

_Verified: 2026-03-24T20:45:00Z_
_Verifier: the agent (gsd-verifier)_
