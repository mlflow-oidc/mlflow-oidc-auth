# Phase 4: Workspace Management UI - Research

**Researched:** 2026-03-23
**Domain:** React/TypeScript frontend — workspace management feature module
**Confidence:** HIGH

## Summary

Phase 4 adds a workspace management UI to the existing React admin application. The backend APIs are fully implemented (Phase 3): 8 CRUD endpoints at `/api/3.0/mlflow/permissions/workspaces/{workspace}/users|groups`, and MLflow core's `ListWorkspaces` endpoint at `/api/3.0/mlflow/workspaces` (GET) provides the workspace list (filtered by the plugin's after_request hook).

The existing frontend codebase has mature, well-established patterns for every concern: list pages, detail/permissions pages, data hooks, service layer, CRUD operations, navigation, and feature flags. This phase requires zero new libraries, frameworks, or architectural innovations — it's strictly pattern replication with workspace-specific semantics. The only infrastructure change is exposing `workspaces_enabled` in the backend config.json endpoint and consuming it in the `RuntimeConfig` type.

**Primary recommendation:** Follow existing patterns exactly — create `src/features/workspaces/` feature module mirroring the experiments/groups pattern, add workspace API endpoints to `api-endpoints.ts`, add workspace data hooks to `core/hooks/`, add "Workspaces" sidebar link gated on `workspaces_enabled` config flag, and add routes in `app.tsx`.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| WSMGMT-04 | React workspace management feature module with workspace list view, workspace detail view, and member management (users + groups) | Workspace list from `/api/3.0/mlflow/workspaces` (MLflow core, filtered), detail via workspace permission CRUD API at `/api/3.0/mlflow/permissions/workspaces/{workspace}/users\|groups`. Follows experiments-page.tsx (list) and entity-permissions-page-layout.tsx (detail) patterns |
| WSMGMT-05 | Workspace switcher component in admin UI navigation for workspace-scoped permission views | Sidebar data function (`getSidebarData`) already uses feature flags. Workspace switcher is a header/sidebar dropdown gated on `workspaces_enabled` from RuntimeConfig |
| WSMGMT-06 | Admin-managed workspace-to-user assignment UI as fallback when OIDC doesn't send workspace claims | Covered by workspace detail view's member management: grant-permission-modal.tsx pattern for adding users/groups with permission levels. Admin check via `currentUser?.is_admin` |
</phase_requirements>

## Project Constraints (from AGENTS.md)

- **Conventional Commits** required: `^(feat|fix|chore|docs|style|ci|refactor|perf|test|build)(\([\w-]+\))?: .+$`
- **Black** formatter for Python (line-length 160)
- **Prettier** for TypeScript/React
- **Pre-commit hooks** enforced
- Python test runner: **pytest** with `pytest-asyncio` (mode `auto`)
- Frontend test runner: **Vitest** with jsdom, Testing Library, co-located `.test.tsx` files
- Frontend coverage thresholds: 80% statements, branches, functions, lines
- **No new frameworks** — React 19, React Router 7, Tailwind CSS 4, FontAwesome 7 only
- Kebab-case for component/module files: `workspace-list-page.tsx`, `use-workspace-permissions.ts`
- PascalCase for component names: `WorkspaceListPage`, `WorkspaceDetailPage`
- Feature modules at `src/features/<name>/` with optional `components/`, `hooks/`, `utils/` subdirectories

## Standard Stack

### Core (existing — no new dependencies)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| React | 19.1 | UI framework | Already in use |
| React Router | 7.9 | Client-side routing | Already in use |
| Tailwind CSS | 4 | Styling | Already in use |
| FontAwesome | 7.1 | Icons | Already in use |
| Vitest | 4.0 | Testing | Already in use |
| Testing Library (React) | 16.3 | Component testing | Already in use |

### Supporting (existing — no new dependencies)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| @fortawesome/free-solid-svg-icons | 7.1 | Icon definitions | Workspace sidebar icon (`faBuilding` or `faLayerGroup`) |
| dompurify | 3.3 | HTML sanitization | Not needed for this phase |

### Alternatives Considered

None. This phase uses exclusively existing dependencies. No new libraries needed.

## Architecture Patterns

### Recommended Project Structure

```
web-react/src/
├── features/
│   └── workspaces/                          # NEW feature module
│       ├── workspaces-page.tsx              # Workspace list page
│       ├── workspaces-page.test.tsx         # List page tests
│       ├── workspace-detail-page.tsx        # Workspace detail (members)
│       ├── workspace-detail-page.test.tsx   # Detail page tests
│       └── components/
│           ├── workspace-members-manager.tsx # User+group CRUD table
│           └── workspace-members-manager.test.tsx
├── core/
│   ├── configs/
│   │   └── api-endpoints.ts                # ADD workspace endpoints
│   ├── hooks/
│   │   ├── use-all-workspaces.ts           # NEW hook
│   │   ├── use-all-workspaces.test.tsx     # NEW test
│   │   ├── use-workspace-users.ts          # NEW hook
│   │   ├── use-workspace-users.test.tsx    # NEW test
│   │   ├── use-workspace-groups.ts         # NEW hook
│   │   └── use-workspace-groups.test.tsx   # NEW test
│   └── services/
│       └── workspace-service.ts            # NEW fetcher functions
│       └── workspace-service.test.ts       # NEW test
├── shared/
│   ├── components/
│   │   └── sidebar-data.ts                 # MODIFY: add workspace link
│   ├── services/
│   │   └── runtime-config.ts               # MODIFY: add workspaces_enabled
│   └── types/
│       └── entity.ts                        # MODIFY: add workspace types
└── app.tsx                                  # MODIFY: add workspace routes
```

### Pattern 1: List Page (follow experiments-page.tsx)

**What:** Workspace list page displays all workspaces the current user can access.
**When to use:** For `/workspaces` route.
**Example:**

```tsx
// Source: web-react/src/features/experiments/experiments-page.tsx (existing pattern)
export default function WorkspacesPage() {
  const { searchTerm, submittedTerm, handleInputChange, handleSearchSubmit, handleClearSearch } = useSearch();
  const { allWorkspaces, isLoading, error, refresh } = useAllWorkspaces();

  const filteredWorkspaces = (allWorkspaces || []).filter(ws =>
    ws.name.toLowerCase().includes(submittedTerm.toLowerCase())
  );

  const columns: ColumnConfig<WorkspaceListItem>[] = [
    { header: "Workspace Name", render: (item) => item.name },
    { header: "Description", render: (item) => item.description || "—" },
    { header: "Permissions", render: (item) => (
      <RowActionButton entityId={item.name} route="/workspaces" buttonText="Manage members" />
    )},
  ];

  return (
    <PageContainer title="Workspaces">
      <PageStatus isLoading={isLoading} loadingText="Loading workspaces..." error={error} onRetry={refresh} />
      {!isLoading && !error && (
        <>
          <SearchInput ... />
          <EntityListTable data={filteredWorkspaces} columns={columns} searchTerm={submittedTerm} />
        </>
      )}
    </PageContainer>
  );
}
```

### Pattern 2: Detail/Members Page (follow entity-permissions-page-layout.tsx)

**What:** Workspace detail page shows users and groups with their permission levels, with ability to add/edit/remove.
**When to use:** For `/workspaces/:workspaceName` route.
**Example:**

```tsx
// Source: web-react/src/features/experiments/experiment-permissions-page.tsx (existing pattern)
export default function WorkspaceDetailPage() {
  const { workspaceName } = useParams<{ workspaceName: string }>();
  const { users, isLoading: isUsersLoading, error: usersError, refetch: refreshUsers } = useWorkspaceUsers({ workspace: workspaceName });
  const { groups, isLoading: isGroupsLoading, error: groupsError, refetch: refreshGroups } = useWorkspaceGroups({ workspace: workspaceName });

  // Combine and display in EntityPermissionsManager-like component
  // with workspace-specific CRUD operations
}
```

### Pattern 3: Data Hook (follow use-all-experiments.ts)

**What:** Hook wrapping `useApi<T>` with a service fetcher.
**When to use:** For all workspace data needs.
**Example:**

```tsx
// Source: web-react/src/core/hooks/use-all-experiments.ts (existing pattern)
export function useAllWorkspaces() {
  const { data: allWorkspaces, isLoading, error, refetch: refresh } = useApi<WorkspaceListItem[]>(fetchAllWorkspaces);
  return { allWorkspaces, isLoading, error, refresh };
}
```

### Pattern 4: API Endpoint Definition (follow api-endpoints.ts)

**What:** Workspace endpoints added to existing endpoint maps.
**When to use:** For all workspace API calls.
**Example:**

```ts
// Note: workspace API uses v3.0 prefix, not v2.0
export const STATIC_API_ENDPOINTS = {
  // ... existing
  ALL_WORKSPACES: "/api/3.0/mlflow/workspaces",  // MLflow core ListWorkspaces
} as const;

export const DYNAMIC_API_ENDPOINTS = {
  // ... existing
  WORKSPACE_USERS: (workspace: string) =>
    `/api/3.0/mlflow/permissions/workspaces/${encodeURIComponent(workspace)}/users`,
  WORKSPACE_GROUPS: (workspace: string) =>
    `/api/3.0/mlflow/permissions/workspaces/${encodeURIComponent(workspace)}/groups`,
  WORKSPACE_USER: (workspace: string, username: string) =>
    `/api/3.0/mlflow/permissions/workspaces/${encodeURIComponent(workspace)}/users/${encodeURIComponent(username)}`,
  WORKSPACE_GROUP: (workspace: string, groupName: string) =>
    `/api/3.0/mlflow/permissions/workspaces/${encodeURIComponent(workspace)}/groups/${encodeURIComponent(groupName)}`,
} as const;
```

### Pattern 5: Feature Flag Gating (follow gen_ai_gateway_enabled)

**What:** Workspace UI gated on `workspaces_enabled` config flag.
**When to use:** In sidebar, routing, and any workspace-conditional UI.
**Example:**

```ts
// RuntimeConfig type (runtime-config.ts)
export type RuntimeConfig = {
  basePath: string;
  uiPath: string;
  provider: string;
  authenticated: boolean;
  gen_ai_gateway_enabled: boolean;
  workspaces_enabled: boolean;  // NEW
};

// sidebar-data.ts
export const getSidebarData = (isAdmin: boolean, genAiGatewayEnabled: boolean, workspacesEnabled: boolean): NavLinkData[] => {
  // ... existing
  if (workspacesEnabled) {
    sidebarContent = [...sidebarContent, { label: "Workspaces", href: "/workspaces", isInternalLink: true, icon: faBuilding }];
  }
  // ...
};
```

### Pattern 6: Service Fetcher (follow entity-service.ts)

**What:** API fetcher functions using `createStaticApiFetcher` and `createDynamicApiFetcher`.
**When to use:** For all workspace data fetching.
**Example:**

```ts
// workspace-service.ts
export const fetchAllWorkspaces = createStaticApiFetcher<WorkspaceListItem[]>({
  endpointKey: "ALL_WORKSPACES",
  responseType: [] as WorkspaceListItem[],
});

export const fetchWorkspaceUsers = createDynamicApiFetcher<WorkspaceUserPermission[], "WORKSPACE_USERS">({
  endpointKey: "WORKSPACE_USERS",
  responseType: [] as WorkspaceUserPermission[],
});

export const fetchWorkspaceGroups = createDynamicApiFetcher<WorkspaceGroupPermission[], "WORKSPACE_GROUPS">({
  endpointKey: "WORKSPACE_GROUPS",
  responseType: [] as WorkspaceGroupPermission[],
});
```

### Anti-Patterns to Avoid

- **Don't add Redux/Zustand/etc.:** Use existing React Context + `useApi` pattern
- **Don't create workspace-specific CRUD abstractions:** Reuse `request()` from `api-utils.ts` directly (following `use-permissions-management.ts` pattern)
- **Don't create a new layout component:** Use existing `ProtectedLayoutRoute` → `MainLayout` → `PageContainer` pattern
- **Don't hard-code workspace API version:** Use the endpoint constants from `api-endpoints.ts`
- **Don't bypass feature flag:** All workspace UI must be gated on `workspaces_enabled` from RuntimeConfig

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Data fetching | Custom fetch hooks | `useApi<T>` + `createStaticApiFetcher`/`createDynamicApiFetcher` | Handles loading, error, abort, auth gating |
| List tables | Custom table component | `EntityListTable` + `ColumnConfig<T>` | Consistent styling, search, empty states |
| Permission CRUD | Custom CRUD logic | Follow `usePermissionsManagement` hook pattern | Toast feedback, loading states, error handling |
| Modals | Custom modal component | `Modal`, `GrantPermissionModal` pattern | Consistent styling, accessibility |
| Permission select | Custom dropdown | `PermissionLevelSelect` | Already handles all 5 permission levels |
| Search/filter | Custom search | `useSearch` + `SearchInput` | Consistent search UX with submit/clear |
| Page layout | Custom layout | `PageContainer` + `PageStatus` | Loading, error, title patterns |
| URL encoding | Manual encoding | `encodeURIComponent` in endpoint functions | Already standard in DYNAMIC_API_ENDPOINTS |
| Feature flag | Prop drilling | `useRuntimeConfig()` hook | Already available via context |
| Toast notifications | Custom notification | `useToast()` from `toast/use-toast.ts` | Consistent success/error feedback |

**Key insight:** The workspace UI is entirely achievable through composition of existing shared components and patterns. No custom infrastructure is needed.

## Common Pitfalls

### Pitfall 1: Wrong API Version Prefix

**What goes wrong:** Using `/api/2.0/mlflow/...` for workspace endpoints when they're at `/api/3.0/mlflow/...`
**Why it happens:** All existing frontend endpoints use v2.0. Workspaces are the first v3.0 endpoints.
**How to avoid:** Workspace list is at `/api/3.0/mlflow/workspaces` (MLflow core). Workspace permissions are at `/api/3.0/mlflow/permissions/workspaces/...` (plugin). Hardcode the correct prefix in endpoint constants.
**Warning signs:** 404 responses when calling workspace APIs.

### Pitfall 2: ListWorkspaces Response Shape

**What goes wrong:** Expecting workspace list at a plugin endpoint when it comes from MLflow core.
**Why it happens:** All other list endpoints (`ALL_EXPERIMENTS`, `ALL_MODELS`, etc.) are plugin endpoints at `/api/2.0/mlflow/permissions/...`. But workspace list comes from MLflow core at `/api/3.0/mlflow/workspaces` and returns `{ workspaces: [{ name, description, default_artifact_root }] }`.
**How to avoid:** The frontend fetcher must extract the `workspaces` array from the response: `fetchAllWorkspaces` should handle the wrapper object. Or define a response type that matches the MLflow protobuf: `{ workspaces: WorkspaceListItem[] }`.
**Warning signs:** Data appears as `undefined` or shows the wrapper object instead of the array.

### Pitfall 3: Missing Feature Flag in config.json

**What goes wrong:** Workspace sidebar link and routes render unconditionally, breaking deployments without workspaces enabled.
**Why it happens:** Backend config.json endpoint (`/oidc/ui/config.json`) doesn't currently include `workspaces_enabled`.
**How to avoid:** Add `"workspaces_enabled": config.MLFLOW_ENABLE_WORKSPACES` to the backend `serve_spa_config` function in `mlflow_oidc_auth/routers/ui.py`, and add `workspaces_enabled: boolean` to the `RuntimeConfig` type.
**Warning signs:** Workspace link always visible in sidebar, or never visible despite feature being enabled.

### Pitfall 4: Sidebar Data Function Signature Change

**What goes wrong:** Existing callers of `getSidebarData(isAdmin, genAiGatewayEnabled)` break when signature changes.
**Why it happens:** Adding `workspacesEnabled` parameter changes the function signature.
**How to avoid:** Update ALL callers: `sidebar.tsx` and `sidebar-data.test.ts`. The function currently has exactly 2 callers: the Sidebar component and its test.
**Warning signs:** TypeScript compilation errors, test failures.

### Pitfall 5: Workspace Name URL Encoding

**What goes wrong:** Workspace names with special characters break routing or API calls.
**Why it happens:** Workspace names are used in URL path segments (e.g., `/workspaces/:workspaceName`).
**How to avoid:** Use `encodeURIComponent()` in endpoint functions (already standard practice in all `DYNAMIC_API_ENDPOINTS`). Use `useParams()` return value directly (React Router auto-decodes).
**Warning signs:** 404 errors for workspaces with spaces or special characters.

### Pitfall 6: Workspace Permission CRUD Body Shape

**What goes wrong:** POST/PATCH requests fail with validation errors.
**Why it happens:** Workspace user permission body is `{ username, permission }` (not `{ name, permission }`). Workspace group permission body is `{ group_name, permission }` (not `{ name, permission }`). This differs slightly from existing resource permission patterns.
**How to avoid:** Match the Pydantic models exactly: `WorkspaceUserPermissionRequest` expects `username` + `permission`; `WorkspaceGroupPermissionRequest` expects `group_name` + `permission`.
**Warning signs:** 422 Unprocessable Entity responses from the API.

### Pitfall 7: Non-Admin Workspace MANAGE Users

**What goes wrong:** UI only shows CUD buttons for admins, preventing workspace MANAGE users from managing members.
**Why it happens:** Existing code often gates management actions on `currentUser?.is_admin`. But WSMGMT-03 allows workspace MANAGE users to manage members.
**How to avoid:** The workspace detail page should show CUD controls for both admin users AND users with MANAGE permission on the workspace. The backend already enforces proper authorization via `check_workspace_manage_permission` dependency — the UI just needs to not hide the buttons unnecessarily. Simplest approach: always show CUD buttons and let the backend reject unauthorized requests (with proper error handling).
**Warning signs:** Non-admin workspace managers can't see add/edit/remove buttons.

## Code Examples

### Workspace Types (to add to entity.ts)

```ts
// Source: MLflow protobuf Workspace message + plugin Pydantic models
export type WorkspaceListItem = {
  name: string;
  description: string;
  default_artifact_root: string;
};

export type WorkspaceListResponse = {
  workspaces: WorkspaceListItem[];
};

export type WorkspaceUserPermission = {
  workspace: string;
  username: string;
  permission: PermissionLevel;
};

export type WorkspaceGroupPermission = {
  workspace: string;
  group_name: string;
  permission: PermissionLevel;
};
```

### Backend Config Change (ui.py)

```python
# Source: mlflow_oidc_auth/routers/ui.py — serve_spa_config function
# Add workspaces_enabled to the config.json response:
return JSONResponse(
    content={
        "basePath": base_path,
        "uiPath": f"{base_path}{UI_ROUTER_PREFIX}",
        "provider": config.OIDC_PROVIDER_DISPLAY_NAME,
        "authenticated": authenticated,
        "gen_ai_gateway_enabled": config.OIDC_GEN_AI_GATEWAY_ENABLED,
        "workspaces_enabled": config.MLFLOW_ENABLE_WORKSPACES,  # NEW
    }
)
```

### Workspace Data Hook Pattern

```ts
// Source: web-react/src/core/hooks/use-all-experiments.ts (pattern)
import { fetchAllWorkspaces } from "../services/workspace-service";
import type { WorkspaceListItem, WorkspaceListResponse } from "../../shared/types/entity";
import { useApi } from "./use-api";

export function useAllWorkspaces() {
  // Note: MLflow ListWorkspaces returns { workspaces: [...] }, need to unwrap
  const { data, isLoading, error, refetch: refresh } = useApi<WorkspaceListResponse>(fetchAllWorkspaces);
  const allWorkspaces = data?.workspaces ?? null;
  return { allWorkspaces, isLoading, error, refresh };
}
```

### Route Registration Pattern

```tsx
// Source: web-react/src/app.tsx (existing pattern)
const WorkspacesPage = React.lazy(() => import("./features/workspaces/workspaces-page"));
const WorkspaceDetailPage = React.lazy(() => import("./features/workspaces/workspace-detail-page"));

// In Routes:
<Route path="/workspaces" element={<ProtectedLayoutRoute><WorkspacesPage /></ProtectedLayoutRoute>} />
<Route path="/workspaces/:workspaceName" element={<ProtectedLayoutRoute><WorkspaceDetailPage /></ProtectedLayoutRoute>} />
```

### CRUD Operations Pattern (workspace members)

```ts
// Source: web-react/src/features/permissions/hooks/use-permissions-management.ts (pattern)
// Workspace member CRUD is simpler than resource permissions — no resource type switching

const handleGrantUserPermission = async (username: string, permission: PermissionLevel) => {
  await request(DYNAMIC_API_ENDPOINTS.WORKSPACE_USERS(workspaceName), {
    method: "POST",
    body: JSON.stringify({ username, permission }),
  });
  showToast(`Permission for ${username} has been granted`, "success");
  refresh();
};

const handleUpdateUserPermission = async (username: string, permission: PermissionLevel) => {
  await request(DYNAMIC_API_ENDPOINTS.WORKSPACE_USER(workspaceName, username), {
    method: "PATCH",
    body: JSON.stringify({ username, permission }),
  });
};

const handleDeleteUserPermission = async (username: string) => {
  await request(DYNAMIC_API_ENDPOINTS.WORKSPACE_USER(workspaceName, username), {
    method: "DELETE",
  });
};
```

### Test Pattern

```tsx
// Source: web-react/src/features/experiments/experiments-page.test.tsx (pattern)
const mockUseAllWorkspaces: Mock<() => { allWorkspaces: WorkspaceListItem[] | null; isLoading: boolean; error: Error | null; refresh: () => void }> = vi.fn();

vi.mock("../../core/hooks/use-all-workspaces", () => ({
  useAllWorkspaces: () => mockUseAllWorkspaces(),
}));

// Mock shared components
vi.mock("../../shared/components/page/page-container", () => ({
  default: ({ children, title }: { children: React.ReactNode; title: string }) => (
    <div data-testid="page-container" title={title}>{children}</div>
  ),
}));

describe("WorkspacesPage", () => {
  it("renders workspace list", () => {
    mockUseAllWorkspaces.mockReturnValue({
      isLoading: false, error: null, refresh: vi.fn(),
      allWorkspaces: [{ name: "default", description: "Default workspace", default_artifact_root: "" }],
    });
    render(<WorkspacesPage />);
    expect(screen.getByText("default")).toBeInTheDocument();
  });
});
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| v2.0 API prefix | v3.0 API prefix for workspace endpoints | MLflow 3.10 | Workspace endpoints use `/api/3.0/` not `/api/2.0/` |
| No workspace concept | Workspace protobuf messages + REST endpoints | MLflow 3.10 | `ListWorkspaces` returns workspace objects with name, description, default_artifact_root |

**Deprecated/outdated:**
- Nothing in the frontend stack is deprecated. React 19, Router 7, Tailwind 4, Vite (rolldown-vite) are all current.

## Open Questions

1. **Workspace Switcher Scope (WSMGMT-05)**
   - What we know: The requirement says "workspace switcher component in admin UI navigation for workspace-scoped permission views"
   - What's unclear: Does "workspace-scoped permission views" mean filtering the existing experiments/models/etc. lists by workspace? Or just a link to the workspace detail page? The current architecture doesn't have workspace-scoped views for experiments — the after_request hook does filtering server-side but doesn't scope by workspace in the UI.
   - Recommendation: Implement as a simple navigation element in the sidebar that links to `/workspaces` (workspace list page), not as a global workspace context switcher. A full workspace context switcher would require passing `X-MLFLOW-WORKSPACE` header in all API calls, which is a much larger change. The workspace list page itself serves as the "switcher" — users click through to manage individual workspaces.

2. **WSMGMT-06 Admin-Only vs MANAGE Permission**
   - What we know: WSMGMT-06 says "Admin-managed workspace-to-user assignment UI". The backend (WSMGMT-03) allows workspace MANAGE users to manage members.
   - What's unclear: Should the UI restrict CUD to admins only (matching WSMGMT-06's "admin-managed" wording) or allow MANAGE users too (matching WSMGMT-03)?
   - Recommendation: Allow both admins and MANAGE users to see CUD controls. The backend already enforces the correct authorization. The UI should not be more restrictive than the API. The requirement wording "admin-managed" refers to the use case (admin fallback when OIDC doesn't provide claims), not a strict admin-only restriction.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node.js | Frontend build & tests | ✓ | v25.8.1 | — |
| Yarn | Package management | ✓ | 1.22.22 | — |
| Vitest | Frontend testing | ✓ | 4.0.16 (via package.json) | — |
| Python | Backend config change | ✓ | 3.12 | — |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** None.

## Sources

### Primary (HIGH confidence)
- Codebase analysis — web-react/src/ directory structure, all feature modules, routing, hooks, services, types (direct file reads)
- Codebase analysis — mlflow_oidc_auth/routers/workspace_permissions.py (8 CRUD endpoints, Pydantic models)
- Codebase analysis — mlflow_oidc_auth/routers/ui.py (config.json endpoint)
- Codebase analysis — mlflow_oidc_auth/config.py (MLFLOW_ENABLE_WORKSPACES flag)
- Codebase analysis — mlflow_oidc_auth/hooks/after_request.py (_filter_list_workspaces handler)
- MLflow protobuf inspection — Workspace message has fields: name, description, default_artifact_root
- MLflow endpoint inspection — ListWorkspaces at `/api/3.0/mlflow/workspaces` (GET)

### Secondary (MEDIUM confidence)
- None needed — all findings based on direct codebase inspection

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies, fully existing stack
- Architecture: HIGH — all patterns verified by reading existing feature modules
- Pitfalls: HIGH — identified from direct API analysis and codebase patterns
- API integration: HIGH — backend endpoints verified by reading router code + Pydantic models + protobuf inspection

**Research date:** 2026-03-23
**Valid until:** 2026-04-23 (stable — no moving parts, pure pattern replication)
