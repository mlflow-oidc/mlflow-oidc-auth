# Project Research Summary

**Project:** MLflow OIDC Auth — v1.1 Workspace Management
**Domain:** Multi-tenant workspace lifecycle, permission management, and scoped resource filtering for an MLflow auth plugin
**Researched:** 2026-03-24
**Confidence:** HIGH

## Executive Summary

v1.1 completes the workspace story started in v1.0. The foundation is solid: feature flags, permission tables, TTLCache, before_request hooks, workspace-aware AuthContext, and basic admin UI all exist. What's missing is workspace CRUD management (create/update/delete through the plugin), a global workspace picker to scope the admin UI, workspace-aware search result filtering to prevent cross-tenant data leakage, and regex-based workspace permissions for bulk access rules. These five features close the gap between "workspace permissions exist" and "workspaces are fully manageable."

The recommended approach requires zero new libraries — the existing stack (FastAPI, Flask, SQLAlchemy, React 19, TailwindCSS) handles everything. The only dependency change is pinning `cachetools>=5.5.0` (already used transitively). The key architectural insight is that workspace CRUD doesn't need an HTTP proxy: MLflow's Flask app already serves workspace endpoints through the WSGI bridge, and the plugin's before_request/after_request hooks already intercept them. However, a FastAPI proxy router is still valuable for the admin UI because it gives pre/post-processing control (auto-granting MANAGE on create, cascading permission deletes). The regex workspace permission implementation follows a proven pattern used by 8+ existing resource types.

The primary risks are: (1) cross-workspace data leakage in search results if filtering checks the request's workspace header instead of each experiment's actual workspace — this is a security-critical correctness issue; (2) O(N×M) performance degradation in search filtering when many workspaces exist; (3) TTLCache invalidation gaps when regex permissions change, since regex rules affect an unpredictable set of cache entries. All three are well-understood and have clear mitigation strategies documented in the pitfalls research.

## Key Findings

### Recommended Stack

No new Python or JavaScript libraries needed. The existing stack covers all v1.1 requirements. The only change: pin `cachetools>=5.5.0` as a direct dependency (currently transitive-only via MLflow, already used in `workspace_cache.py`).

**Core technologies (unchanged):**
- **FastAPI** — New workspace CRUD proxy router + regex permission endpoints
- **Flask/MLflow** — Handles workspace RPCs natively; plugin intercepts via hooks
- **SQLAlchemy + Alembic** — Two new regex permission tables following existing patterns
- **React 19 + TailwindCSS** — Global workspace picker, CRUD forms; no UI library additions
- **cachetools TTLCache** — Workspace permission caching; extend with regex lookup sources

**Explicitly not adding:** `httpx` for proxy forwarding (Flask handles it), Headless UI/Radix (TailwindCSS sufficient), `zustand`/`jotai` (React Context sufficient), Redis (TTLCache sufficient).

### Expected Features

**Must have (table stakes — v1.1):**
- **TS-01: Workspace CRUD backend** — FastAPI proxy to MLflow's workspace API with auth checks, auto-grant MANAGE on create, cascade permission delete on workspace removal
- **TS-02: Workspace management UI** — Admin page for create/edit/delete workspaces with client-side name validation mirroring MLflow's `WorkspaceNameValidator`
- **TS-03: Global workspace picker** — Header dropdown scoping all admin pages via `X-MLFLOW-WORKSPACE` header injection, persisted in localStorage
- **TS-04: Workspace-scoped search filtering** — after_request hooks filter experiments/models by workspace membership, checking each resource's actual workspace (not just the request header)
- **TS-05: Regex workspace permissions** — Pattern-based access rules (e.g., `team-.*` → READ) with user-regex and group-regex variants, integrated into TTLCache resolution chain

**Should have (differentiators — defer to v1.2):**
- Workspace member/resource counts in list view
- Workspace permission bulk operations
- Workspace picker search/filter for 100+ workspaces
- Auto-create workspace from OIDC claim mapping
- Workspace quick-switch keyboard shortcut

**Anti-features (explicitly not building):**
- Workspace hierarchy/nesting (MLflow model is flat)
- Cross-workspace resource moving (not supported by MLflow)
- Per-workspace RBAC redefinitions
- Direct workspace store access (always proxy through MLflow)

### Architecture Approach

The architecture extends the existing dual-framework pattern: FastAPI handles new CRUD proxy and regex permission endpoints; Flask hooks handle search filtering and permission cascade. A new `WorkspaceContext` React context + module-level store bridges workspace selection to the HTTP client without requiring React Context in the non-React `http.ts` module.

**Major components (new/modified):**
1. **`routers/workspace.py`** (NEW) — Workspace CRUD proxy with FastAPI dependency-based auth (admin for create, MANAGE for update/delete)
2. **`routers/workspace_permissions.py`** (MODIFY) — Add 8 regex/group-regex endpoints following existing pattern
3. **`hooks/after_request.py`** (MODIFY) — Workspace-scoped search filtering checking each experiment's actual workspace
4. **`utils/workspace_cache.py`** (MODIFY) — Extend TTLCache lookup with regex + group-regex sources, add `flush_workspace_cache()` for regex CUD
5. **`repository/workspace_regex_permission.py`** (NEW) — Extends `BaseRegexPermissionRepository` (2 new repo files)
6. **`workspace-provider.tsx` + `workspace-picker.tsx`** (NEW) — Frontend context + header dropdown + module-level store for `http.ts` header injection

### Critical Pitfalls

1. **Cross-workspace data leakage in search filtering** — The after_request filter must check each experiment's *actual* workspace, not just the request's `X-MLFLOW-WORKSPACE` header. If a user searches without a workspace header, they could see experiments from workspaces they don't have access to. **Mitigation:** Resolve each experiment's workspace from the proto response and verify workspace permission for that specific workspace.

2. **O(N×M) search filtering performance** — Post-fetch filtering with per-item permission checks becomes catastrophic when most results are filtered out by workspace. **Mitigation:** Filter by workspace FIRST (cheap string comparison), then apply permission checks. Batch workspace membership lookups. Cap re-fetch iterations at 5-10.

3. **TTLCache invalidation gaps for regex permissions** — Regex changes affect an unpredictable set of cache entries. Selective invalidation is impractical. **Mitigation:** Flush the entire workspace cache on any regex permission CUD operation.

4. **Permission escalation via MANAGE delegation** — Extending workspace update/delete from admin-only to MANAGE users introduces rename attacks and shared workspace disruption. **Mitigation:** Carefully scope what MANAGE allows; consider keeping workspace lifecycle operations admin-only while MANAGE controls only permission assignment.

5. **Feature flag bypass** — Every new workspace code path must check `MLFLOW_ENABLE_WORKSPACES`. **Mitigation:** Gate at the router registration level (don't register workspace routers when flag is false) rather than per-endpoint checks.

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Regex Workspace Permissions (Backend Foundation)

**Rationale:** Pure additive backend change with zero impact on existing functionality. Follows proven pattern (8+ existing implementations). Completes the workspace permission resolution chain so all subsequent features benefit from full 4-source permission resolution.
**Delivers:** 2 new DB tables, 2 new repositories extending base classes, workspace cache with regex/group-regex lookup, 8 new API endpoints on existing router, Alembic migration, `flush_workspace_cache()` function, `cachetools` pinned as direct dependency.
**Addresses:** TS-05 (Regex workspace permissions)
**Avoids:** P4 (TTLCache invalidation) — implement `flush_workspace_cache()` alongside regex CRUD. P10 (Resolution order) — decide on `PERMISSION_SOURCE_ORDER` integration now. P14 (cachetools pinning) — pin as direct dependency in this phase.

### Phase 2: Workspace CRUD Backend + Permission Cascade

**Rationale:** Depends on Phase 1 for complete permission resolution (MANAGE delegation needs regex lookup). Creates the backend API surface for the admin UI. Workspace deletion cascade prevents orphaned permission records.
**Delivers:** New FastAPI workspace CRUD proxy router (5 endpoints), after_request hook for permission cascade on delete, MANAGE delegation for update/delete validators, MLflow error code mapping.
**Addresses:** TS-01 (Workspace CRUD backend)
**Avoids:** P1 (Proxy error conflation) — parse MLflow error codes and map to HTTP statuses. P2 (Permission escalation) — define MANAGE scope before implementing. P6 (Name validation mismatch) — validate in proxy, handle MLflow errors gracefully. P9 (Orphaned permissions) — cascade delete in after_request. P12 (API instability) — abstract MLflow workspace API calls.

### Phase 3: Workspace-Scoped Search Filtering

**Rationale:** Security-critical feature that prevents cross-workspace data leakage. Depends on Phase 1 (workspace cache with regex) for complete permission checks. Can be built in parallel with Phase 2 since it modifies different code paths (after_request filter functions vs. new router).
**Delivers:** Modified `_filter_search_experiments()`, `_filter_search_registered_models()`, `_filter_search_logged_models()` with workspace membership checks.
**Addresses:** TS-04 (Workspace-scoped search filtering)
**Avoids:** P3 (Performance death spiral) — filter workspace FIRST, cap re-fetch iterations. P5 (Feature flag bypass) — check `MLFLOW_ENABLE_WORKSPACES` as first operation. P8 (Hook ordering) — workspace filter before permission filter in each function.

### Phase 4: Workspace Management UI + Global Picker

**Rationale:** Pure frontend phase that depends on all backend work being complete (CRUD proxy, search filtering, regex permissions). Both the management UI and the picker share workspace list data and React context infrastructure — building them together avoids duplicate component work.
**Delivers:** `WorkspaceContext` + `WorkspaceProvider`, `WorkspacePicker` header dropdown, `http.ts` header injection via module-level workspace store, workspace CRUD forms (create/edit/delete), modified admin pages consuming workspace context.
**Addresses:** TS-02 (Workspace management UI), TS-03 (Global workspace picker)
**Avoids:** P7 (Stale context) — React Context + localStorage + validation on load. P11 (Admin vs non-admin lists) — picker naturally shows filtered workspace list. P13 (Header vs URL mismatch) — workspace detail pages ignore picker, picker affects list/search pages only.

### Phase Ordering Rationale

- **Backend-first:** All 3 backend phases can be individually tested, reviewed, and merged without frontend changes. This reduces integration risk.
- **Regex before CRUD:** Counterintuitive but correct — the CRUD proxy's MANAGE delegation requires complete permission resolution (including regex) to avoid security gaps. Having the full permission chain ready means MANAGE authorization is correct from day one.
- **Search filtering parallel-eligible with CRUD:** They touch different files (after_request filter functions vs. new router). Can be developed in parallel branches after Phase 1.
- **Frontend last:** The frontend is a single coherent phase that ties everything together. It can be developed with mock data while backend phases are in progress, but final integration requires all backend work.
- **Feature flag gating in Phase 1:** Router-level conditional registration ensures all new endpoints are invisible when workspaces are disabled.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 2 (Workspace CRUD):** How exactly to proxy requests to the mounted Flask app — `httpx.AsyncClient` vs. direct tracking store access vs. WSGI bridge passthrough. The STACK research found Flask handles it natively through hooks, but FEATURES research recommends a proxy for pre/post-processing control. This tension needs resolution during phase planning.
- **Phase 3 (Search Filtering):** How upstream MLflow exposes experiment→workspace mapping in proto responses. Need to inspect the `Experiment` proto's `workspace` field availability in `SearchExperiments.Response`. If not available, a performance-critical batch lookup is needed.

Phases with standard patterns (skip research-phase):
- **Phase 1 (Regex Permissions):** Exact pattern replicated from 8+ existing implementations. DB models, repos, entities, store methods, router endpoints, cache integration — all have direct templates in the codebase.
- **Phase 4 (Frontend):** Standard React Context + component patterns. All infrastructure hooks (`useAllWorkspaces`, `WorkspaceListItem` types, `fetchAllWorkspaces` service) already exist.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Zero new dependencies. All verified against installed versions and existing usage patterns. |
| Features | HIGH | All 5 features have clear scope, dependency chains, and implementation patterns verified from codebase. MLflow workspace API verified via runtime introspection. |
| Architecture | HIGH | All patterns are extensions of existing codebase patterns (regex repos, after_request hooks, React Context). No novel architecture needed. |
| Pitfalls | HIGH | All 14 pitfalls derived from direct codebase analysis of actual code paths. Prevention strategies reference specific functions and files. |

**Overall confidence:** HIGH — This is an enhancement to a well-understood codebase following established patterns. The v1.0 workspace foundation is solid and well-documented.

### Gaps to Address

- **Experiment→workspace mapping in proto responses:** Need to verify that `SearchExperiments.Response` includes workspace info per experiment. If not, search filtering requires separate tracking store queries (significant performance impact). Resolve during Phase 3 planning.
- **MANAGE delegation scope for workspace CRUD:** Research found tension between allowing MANAGE users to update/delete workspaces (FEATURES) and the security risks of doing so (PITFALLS). Need a clear policy decision: MANAGE = permission management only, or MANAGE = full workspace lifecycle? Resolve during Phase 2 planning.
- **Workspace CRUD proxy implementation approach:** STACK research says Flask handles workspace RPCs natively (no proxy needed). FEATURES/ARCHITECTURE research recommends a FastAPI proxy for better control. The hybrid approach (FastAPI proxy as primary for admin UI, Flask passthrough for SDK clients) needs validation. Resolve during Phase 2 planning.
- **MLflow workspace API stability:** The API is `PUBLIC_UNDOCUMENTED`. No breaking changes observed in 3.10.x, but the proxy should be designed as an abstraction layer. Monitor MLflow release notes.

## Sources

### Primary (HIGH confidence)
- Direct codebase analysis: `hooks/after_request.py`, `hooks/before_request.py`, `validators/workspace.py`, `utils/workspace_cache.py`, `utils/permissions.py`, `repository/_base.py`, `routers/workspace_permissions.py`, `db/models/workspace.py`, `config.py`, `app.py`, `middleware/auth_middleware.py`, `middleware/auth_aware_wsgi_middleware.py`, `bridge/user.py`, `dependencies.py`
- Frontend codebase: `http.ts`, `workspace-service.ts`, `use-all-workspaces.ts`, `header.tsx`, `sidebar-data.ts`, `runtime-config.ts`, `api-endpoints.ts`, `entity.ts`
- MLflow 3.10 runtime introspection: workspace protobuf RPCs (`CreateWorkspace`, `GetWorkspace`, `ListWorkspaces`, `UpdateWorkspace`, `DeleteWorkspace`), `WorkspaceNameValidator`, `WorkspaceDeletionMode`, endpoint registration via `get_endpoints()`

### Secondary (MEDIUM confidence)
- MLflow workspace API stability assessment: `PUBLIC_UNDOCUMENTED` annotation observed in protobuf definitions — API contract not guaranteed across minor versions

### Tertiary (LOW confidence)
- Experiment→workspace mapping in search responses: Assumed available based on MLflow 3.10 `Experiment` entity having a `workspace` field — needs runtime verification with actual search responses

---
*Research completed: 2026-03-24*
*Ready for roadmap: yes*
