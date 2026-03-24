# Domain Pitfalls

**Domain:** Workspace CRUD management, search filtering, regex permissions, and global workspace picker for MLflow OIDC auth plugin
**Researched:** 2026-03-24
**Milestone:** v1.1 Workspace Management
**Confidence:** HIGH — based on direct analysis of the live codebase (v1.0 post-merge), existing patterns, and known upstream API behavior

## Critical Pitfalls

Mistakes that cause data leakage, broken deployments, or require rewrites.

### Pitfall 1: Proxy Error Conflation — MLflow 500s Surfaced as Auth Errors

**What goes wrong:**
The workspace CRUD proxy will forward requests to MLflow's `/api/3.0/mlflow/workspaces` REST API. When MLflow returns an error (workspace doesn't exist, name conflict, internal error), the proxy must distinguish between:
- **MLflow auth errors** (which shouldn't happen — the proxy is a trusted internal caller)
- **MLflow validation errors** (workspace name invalid, already exists)
- **MLflow resource errors** (workspace not found, workspace has resources)
- **MLflow internal errors** (tracking store failure, backend unavailable)

If the proxy blindly wraps all MLflow errors as `500 Internal Server Error` or `403 Forbidden`, the admin UI cannot display actionable error messages. Worse: if MLflow returns a `401` (e.g., the internal request lacks proper auth), the proxy might redirect the user to login instead of showing the actual error.

**Why it happens:**
MLflow's workspace API is `PUBLIC_UNDOCUMENTED` (v3.0). Error response format is not guaranteed stable. Developers might use a simple `httpx.post()` and `if not resp.ok: raise HTTPException(resp.status_code)` without parsing MLflow's error body. The existing pattern in the codebase (direct Flask hooks) never needed to proxy to MLflow — it intercepted requests, not forwarded them.

**Consequences:**
- Users see "Internal Server Error" when they try to create a workspace with a duplicate name
- Admin UI shows generic error toast instead of "Workspace 'prod' already exists"
- Delete fails silently or with cryptic error when workspace has resources
- Difficult to diagnose whether the error is in the proxy or MLflow

**Prevention:**
- Parse MLflow's error response body and extract the error message. MLflow uses protobuf-based error responses with `error_code` and `message` fields.
- Map MLflow error codes to appropriate HTTP status codes in the proxy: `RESOURCE_ALREADY_EXISTS` → 409, `RESOURCE_DOES_NOT_EXIST` → 404, `INVALID_PARAMETER_VALUE` → 400.
- Never surface raw MLflow error responses to clients — the proxy should normalize them into the plugin's standard error format.
- Add a `try/except` around the proxy call that catches `httpx` transport errors separately from MLflow application errors.
- The proxy must authenticate to MLflow as an internal trusted caller. Since the plugin IS the MLflow app (Flask is mounted inside FastAPI), the proxy can call MLflow's tracking store directly via `_get_tracking_store()` rather than making HTTP calls — evaluate this approach first as it avoids the proxy networking complexity entirely.

**Detection:**
- Error responses that say "Internal Server Error" when the user action was obviously wrong (duplicate name, etc.)
- Error responses that include MLflow-internal stack traces
- Network-level errors (connection refused) when MLflow's workspace API is unavailable

**Phase to address:** Workspace CRUD backend phase — first thing to build, foundational for all CRUD operations.

---

### Pitfall 2: Permission Escalation via MANAGE Workspace Delegation on Update/Delete

**What goes wrong:**
Per the milestone spec, MANAGE permission holders (not just admins) can update and delete workspaces. The current `validate_can_update_workspace` and `validate_can_delete_workspace` in `validators/workspace.py` are admin-only:

```python
def validate_can_update_workspace(username: str):
    """Only admins can update workspaces."""
    auth_context = get_auth_context()
    if not auth_context.is_admin:
        return responses.make_forbidden_response()
    return None
```

Changing these to allow MANAGE users introduces escalation risks:
1. **Workspace rename attack**: A MANAGE user renames workspace "production" to "test", then creates a new workspace "production" they control. If any automation or hardcoded references point to "production", they now point to the attacker's workspace.
2. **Workspace deletion of shared workspace**: A MANAGE user with access to a shared workspace deletes it, affecting all other users. The "only if workspace has no resources" check mitigates data loss but doesn't prevent disruption.
3. **Self-granting via workspace permission + workspace MANAGE**: A user with MANAGE on workspace-A can grant themselves MANAGE on workspace-B via the workspace permission CRUD router (if the permission check only verifies MANAGE on the *source* workspace, not the *target*).

**Why it happens:**
MANAGE permission was designed for resource-level delegation (experiments, models). Workspace is a tenant boundary, not a resource — MANAGE on a workspace has higher blast radius than MANAGE on an experiment. The existing `check_workspace_manage_permission` dependency in `dependencies.py` correctly checks MANAGE on the specific workspace, but the validator in the Flask hooks layer uses a different code path.

**Consequences:**
- Privilege escalation: workspace MANAGE user disrupts other workspaces
- Workspace hijacking via rename
- Cascading permission issues if workspace name changes but permissions reference old name

**Prevention:**
- **Separate update/delete authorization from permission management.** MANAGE on a workspace should allow managing *permissions within* the workspace (already implemented), but update/delete of the workspace entity itself could require ADMIN or a dedicated `WORKSPACE_ADMIN` permission level.
- If MANAGE is allowed for update/delete: validate that the workspace rename doesn't collide with existing names (MLflow likely does this, but the proxy should also check). Log all workspace mutations with the acting user.
- For deletion: enforce the "no resources" check in the proxy layer, not just in MLflow. Double-check by querying experiments and models scoped to the workspace before forwarding the delete.
- **Critical**: The workspace permission router (`workspace_permissions.py`) uses `check_workspace_manage_permission` which checks MANAGE on the `workspace` path parameter. This is correct for managing permissions *within* a workspace. But for workspace CRUD, the path parameter IS the workspace being modified — verify the check is against the correct workspace.

**Detection:**
- Audit logs showing non-admin users deleting or renaming workspaces
- Workspace permission records that reference workspace names that no longer exist (orphaned after rename)
- Multiple workspaces created by the same user in rapid succession (workspace squatting)

**Phase to address:** Workspace CRUD backend phase — the authorization model for workspace CRUD must be decided before implementing the proxy.

---

### Pitfall 3: Search Filtering Performance Death Spiral — O(N×M) Permission Checks

**What goes wrong:**
The existing `_filter_search_experiments` and `_filter_search_registered_models` in `after_request.py` already have a performance concern: they iterate every result and call `can_read_experiment()` / `can_read_registered_model()` per item. Each `can_read_*` call triggers `resolve_permission()` which walks the 4-source chain (user → group → regex → group-regex), and with workspaces enabled, adds a workspace fallback lookup via `get_workspace_permission_cached()`.

Adding workspace-scoped search filtering means:
1. First, filter results to only include items belonging to the active workspace
2. Then, apply permission filtering (existing behavior)
3. Re-fetch to fill `max_results` (existing pagination repair loop)

The re-fetch loop (lines 111-131 in `after_request.py`) calls `tracking_store.search_experiments()` repeatedly. Each iteration returns results from ALL workspaces (MLflow's store is not workspace-aware), which are then filtered again. If the active workspace has 10 experiments but there are 10,000 total, the loop fetches many pages to find 10 matching ones.

**Why it happens:**
MLflow's tracking store has no workspace-aware query parameter. The plugin can only filter post-fetch. The existing re-fetch loop was acceptable when filtering was just permission-based (most results are readable), but workspace filtering removes a much larger percentage of results (all other workspaces' resources).

**Consequences:**
- Search endpoints become slow (seconds to tens of seconds) for deployments with many workspaces
- Each re-fetch iteration triggers N permission lookups for results that will be filtered out by workspace
- Database connection pool exhaustion under concurrent search requests
- Pagination breaks: users see empty pages or fewer results than expected
- TTLCache for workspace permissions helps but doesn't eliminate the per-result permission check cost

**Prevention:**
- **Filter by workspace FIRST, before permission checks.** The workspace filter is cheap (string comparison on experiment metadata or a mapping table lookup) while permission checks are expensive (4-source resolution chain + DB queries).
- **Short-circuit the re-fetch loop** with a workspace-aware query if possible. If experiments have a workspace tag/attribute, add it to the filter string passed to MLflow's store. Check if MLflow 3.10 supports `workspace_id` in search requests.
- **Cap the re-fetch iterations.** The current loop has no iteration limit — add a max of 5-10 re-fetch attempts to prevent infinite loops when most results are filtered out.
- **Batch workspace membership checks.** Instead of checking `get_workspace_permission_cached()` per result, get the user's accessible workspaces once and filter results against that set.
- Consider caching the workspace-to-experiment mapping in the plugin's DB to avoid scanning all experiments every search.

**Detection:**
- Search endpoint latency >500ms in APM/monitoring
- Re-fetch loop executing more than 3 iterations per search request (log a warning)
- Users reporting slow experiment/model listing in the admin UI
- Database query count per search request growing linearly with total experiment count

**Phase to address:** Workspace-scoped search filtering phase — this is the core of this feature. Must be profiled with realistic data volumes (1000+ experiments across 10+ workspaces).

---

### Pitfall 4: TTLCache Invalidation Gaps for Regex Workspace Permissions

**What goes wrong:**
The existing workspace permission cache (`workspace_cache.py`) uses `cachetools.TTLCache` with explicit invalidation for user permission CUD operations (`invalidate_workspace_permission(username, workspace)`). Group permission changes rely on TTL expiry only (per decision D-15). Adding regex workspace permissions creates three new invalidation gaps:

1. **Regex permission CUD doesn't invalidate cache.** When an admin adds/modifies/removes a regex workspace permission like `prod-.*` → READ, users whose workspace names match the regex still have stale cache entries. The cache key is `(username, workspace)`, but the regex change affects an unpredictable set of workspace-user combinations.
2. **Regex priority changes don't invalidate cache.** If regex `prod-.*` → READ (priority 1) is changed to `prod-.*` → MANAGE (priority 1), cached entries for all matching workspace-user pairs are stale.
3. **Group-regex workspace permission changes compound the problem.** If a group-regex permission changes, the affected set is (all users in group) × (all workspaces matching regex).

The `_lookup_workspace_permission` function in `workspace_cache.py` currently only checks user-level and group-level permissions:
```python
# User-level workspace permission
try:
    perm = store.get_workspace_permission(workspace, username)
    return get_permission(perm.permission)
except Exception:
    pass
# Group-level workspace permission (highest across user's groups)
try:
    perm = store.get_user_groups_workspace_permission(workspace, username)
    return get_permission(perm.permission)
except Exception:
    pass
```
Regex workspace permissions must be added to this lookup chain, AND the cache invalidation strategy must account for them.

**Why it happens:**
Regex permissions create a many-to-many relationship between permission rules and cached entries. You can't predict which cache entries are affected by a regex change without scanning all cached keys against the new regex — which defeats the purpose of caching.

**Consequences:**
- Users retain old permissions for up to `WORKSPACE_CACHE_TTL_SECONDS` (default 300s = 5 minutes) after regex permission changes
- In security-sensitive environments, 5 minutes of stale access control is unacceptable
- Admins create regex permissions expecting immediate effect, file bug reports when they don't see changes

**Prevention:**
- **On regex permission CUD: flush the entire workspace permission cache.** Regex changes are infrequent (admin operations) and affect an unpredictable set of cache entries. A full cache flush is simpler and safer than selective invalidation. The `_cache` module-level variable can be reset to `None` to trigger re-creation.
- **Add `flush_workspace_cache()` function** alongside existing `invalidate_workspace_permission()`. Call it from the regex workspace permission router.
- **Document the cache behavior** in the admin UI: "Regex permission changes may take up to X seconds to take effect" (with the caveat that full flush makes it immediate).
- **Integration test**: Change a regex workspace permission, immediately verify the affected user's effective permission has changed (not stale from cache).
- Do NOT try to do smart selective invalidation by scanning cache keys against the regex — it's complex, error-prone, and the cache is small (max 1024 entries by default).

**Detection:**
- Admin creates regex permission, user still has old access level
- `WORKSPACE_CACHE_TTL_SECONDS` is set very high (>600s) and regex permission changes appear to "not work"
- Unit tests that mock the cache pass, but integration tests with real cache show stale data

**Phase to address:** Regex workspace permissions phase — the cache invalidation strategy must be designed alongside the regex permission implementation.

---

### Pitfall 5: Workspace Feature Flag Bypass — Inconsistent Gating

**What goes wrong:**
The `MLFLOW_ENABLE_WORKSPACES` feature flag gates workspace behavior throughout the codebase. When adding new workspace features (CRUD proxy, search filtering, regex permissions, workspace picker), every new code path must check this flag. Inconsistencies lead to:

1. **Workspace CRUD endpoints accessible when workspaces disabled.** If the proxy router is registered unconditionally in `get_all_routers()`, users can create/delete workspaces even when the feature is off.
2. **Search filtering applied when workspaces disabled.** If the new `after_request` workspace filter doesn't check `config.MLFLOW_ENABLE_WORKSPACES`, it filters results based on a workspace header that was never meant to be sent.
3. **Regex workspace permissions created when workspaces disabled.** If the regex permission router doesn't gate on the feature flag, permission records accumulate in the database with no effect — then cause unexpected behavior when workspaces are later enabled.
4. **Frontend workspace picker visible when workspaces disabled.** The runtime config must signal to the frontend whether workspaces are enabled.

The existing `_filter_list_workspaces` in `after_request.py` correctly checks:
```python
if not config.MLFLOW_ENABLE_WORKSPACES:
    return
```
But this pattern must be applied consistently to every new code path.

**Why it happens:**
Feature flags require discipline. Every developer adding a new feature must remember to check the flag. The more code paths there are, the more likely one is missed.

**Consequences:**
- Users accidentally interact with workspace features in a non-workspace deployment
- Database accumulates workspace-related records that are confusing when workspaces are later enabled
- Error messages reference workspaces in deployments that don't use them
- Frontend shows workspace UI elements that don't work

**Prevention:**
- **Gate at the router level, not just the endpoint level.** Don't register workspace CRUD and regex permission routers at all when `config.MLFLOW_ENABLE_WORKSPACES` is False. This is a single check in `get_all_routers()` rather than N checks in N endpoints.
- **The existing workspace permission router (`workspace_permissions.py`) should already be conditionally registered** — verify this is the case and follow the same pattern for new routers.
- **Frontend runtime config must include `workspacesEnabled`** flag. The workspace picker component should check this before rendering.
- **Add a decorator or middleware for workspace-required endpoints** that returns 404 (not 403) when workspaces are disabled — "endpoint not found" is more appropriate than "forbidden" for a feature that doesn't exist.
- **Search filtering in after_request** must check the flag as the FIRST thing, before any workspace-related processing.
- **Integration test**: With `MLFLOW_ENABLE_WORKSPACES=false`, verify all workspace-related endpoints return 404 and search filtering doesn't apply workspace scoping.

**Detection:**
- Workspace-related endpoints returning 200/201 when `MLFLOW_ENABLE_WORKSPACES=false`
- Workspace permission records in database of a non-workspace deployment
- Frontend showing workspace picker in a deployment where workspaces aren't enabled

**Phase to address:** All phases — must be checked during every workspace feature addition. Best addressed with a router-level gate in the first phase.

---

## Moderate Pitfalls

Mistakes that cause confusion, regressions, or significant rework but not security issues.

### Pitfall 6: Workspace Name Validation Mismatch Between Proxy and MLflow

**What goes wrong:**
The milestone specifies DNS-safe workspace naming rules. The proxy validates workspace names before forwarding to MLflow, but MLflow has its own validation. Three failure modes:
1. **Proxy allows names MLflow rejects**: User gets past proxy validation, MLflow returns 400. Error message comes from MLflow, not the proxy — confusing UX.
2. **Proxy rejects names MLflow allows**: Proxy is stricter than necessary. Legitimate workspace names are blocked.
3. **Proxy doesn't validate at all**: MLflow's error messages for invalid names may be cryptic (protobuf error codes) or change between versions.

DNS-safe means: lowercase alphanumeric, hyphens allowed (not at start/end), max 63 chars, no dots. But MLflow may have different rules — it's `PUBLIC_UNDOCUMENTED`.

**Prevention:**
- Validate in the proxy with a documented regex (e.g., `^[a-z][a-z0-9-]{0,61}[a-z0-9]$`). Return a clear 400 error: "Workspace name must be DNS-safe: lowercase alphanumeric and hyphens, 2-63 characters."
- Also handle MLflow validation errors gracefully — if MLflow rejects a name the proxy accepted, log a warning and return the MLflow error.
- **Test with edge cases**: single character, 63 characters, 64 characters, leading/trailing hyphen, uppercase, unicode, empty string, reserved names ("default", "admin").
- Decide whether "default" is a reserved name that can't be created/deleted/renamed.

**Phase to address:** Workspace CRUD backend phase.

---

### Pitfall 7: Global Workspace Picker State Management — Stale Context After Navigation

**What goes wrong:**
The global workspace picker in the UI header scopes all admin pages to the selected workspace. This introduces global state that must be:
1. Persisted across page navigations (React Router transitions)
2. Persisted across page refreshes (browser storage)
3. Synchronized with the `X-MLFLOW-WORKSPACE` header sent with API requests
4. Invalidated when the user's workspace permissions change (e.g., removed from a workspace)
5. Defaulted correctly on first load (user's primary workspace? "default"?)

Common failures:
- User selects workspace "prod", navigates to experiments page, page loads with "default" workspace because the context was lost.
- User is removed from workspace "prod" by admin, but the picker still shows "prod" and all API calls fail with 403.
- Two browser tabs with different workspace selections — which one wins?
- The HTTP client (`http.ts`) doesn't include `X-MLFLOW-WORKSPACE` header, so API calls go to the "default" workspace regardless of picker selection.

**Why it happens:**
The current frontend has no global workspace state. The `http.ts` module is a simple fetch wrapper with no request interceptor pattern. Adding a global header requires modifying the HTTP layer to read from a React context or global store — something the current architecture doesn't support.

**Prevention:**
- **Use React Context for workspace state** with `localStorage` persistence. Create a `WorkspaceContext` that wraps the app and provides `{currentWorkspace, setCurrentWorkspace}`.
- **Modify `http.ts` to accept custom headers** or create a workspace-aware wrapper that injects `X-MLFLOW-WORKSPACE` from the context. Since `http.ts` already accepts `headers` in options, the workspace hook can pass it: `http(url, { headers: { 'X-MLFLOW-WORKSPACE': currentWorkspace } })`.
- **On workspace list load, validate the persisted selection** — if the persisted workspace is no longer in the user's accessible list, reset to "default" or the first accessible workspace.
- **Don't use `localStorage` workspace key across users** — prefix with username or clear on logout.
- **Show a loading state** while the workspace list is being fetched on first load, before allowing any admin page interactions.

**Detection:**
- API calls missing `X-MLFLOW-WORKSPACE` header (check network tab)
- Admin pages showing data from the wrong workspace after navigation
- 403 errors after workspace picker selection change
- Workspace picker showing workspaces the user no longer has access to

**Phase to address:** Global workspace picker UI phase — this is a cross-cutting frontend architecture change.

---

### Pitfall 8: after_request Hook Ordering — Workspace Filter vs Permission Filter Conflict

**What goes wrong:**
The existing `AFTER_REQUEST_PATH_HANDLERS` in `after_request.py` maps protobuf request classes to handler functions. Each handler runs independently via `after_request_hook`. Adding workspace-scoped search filtering means adding a new dimension to the existing `_filter_search_experiments` and `_filter_search_registered_models` functions (or adding new handlers).

Two approaches, both with pitfalls:
1. **Modify existing filter functions** to add workspace filtering: The functions are already complex (40-50 lines each with pagination repair). Adding workspace filtering increases complexity and makes the function do two different kinds of filtering. Hard to test, hard to maintain.
2. **Add separate workspace filter handlers**: The `AFTER_REQUEST_HANDLERS` dict maps each `(path, method)` to a single handler. You can't have two handlers for the same endpoint. So you'd need a composition pattern that doesn't exist.

The `_filter_list_workspaces` function (line 413-427) shows the correct pattern for workspace-specific filtering, but it operates on a different endpoint (ListWorkspaces), not on the search endpoints.

**Why it happens:**
The after_request hook architecture assumes one handler per endpoint. Workspace scoping is a cross-cutting concern that should apply to multiple search endpoints, but the current architecture doesn't support composing multiple handlers.

**Prevention:**
- **Modify existing filter functions** (option 1) but extract the workspace filtering into a reusable helper:
  ```python
  def _filter_by_workspace(items, workspace_extractor):
      """Filter items to only include those in the active workspace."""
      if not config.MLFLOW_ENABLE_WORKSPACES:
          return items
      workspace = get_request_workspace()
      if not workspace:
          return items
      return [item for item in items if workspace_extractor(item) == workspace]
  ```
- Call the workspace filter BEFORE the permission filter in each function (workspace filtering is cheap, permission filtering is expensive).
- **Do NOT create a generic "filter chain" abstraction** — it's overengineering for 3-4 search endpoints. Just add workspace filtering to each existing function.
- **Test each modified function** with: workspaces disabled (no filtering), workspaces enabled with matching workspace, workspaces enabled with non-matching workspace, no workspace header (admin user).

**Detection:**
- Search results include items from other workspaces
- Search results are empty when they should contain items (over-filtering)
- Permission filtering performance regression (workspace filtering not applied first)

**Phase to address:** Workspace-scoped search filtering phase — must be implemented within the existing filter functions.

---

### Pitfall 9: Workspace Deletion Cascade — Orphaned Permissions

**What goes wrong:**
When a workspace is deleted (via the proxy to MLflow), the plugin's own `workspace_permissions` and `workspace_group_permissions` tables still contain rows referencing the deleted workspace name. Additionally, any workspace regex permissions that matched the deleted workspace's name are now matching a non-existent workspace.

Unlike experiments and models, which have cascade delete handlers in `after_request.py`, there's no workspace deletion cascade in the current codebase. The `validate_can_delete_workspace` only checks admin status — it doesn't trigger any cleanup.

**Why it happens:**
Workspace permission records use `workspace` (a string name) as part of their composite primary key, not a foreign key to a workspace table (because the plugin doesn't own the workspace entity — MLflow does). There's no ON DELETE CASCADE because there's no FK relationship.

**Consequences:**
- `workspace_permissions` table accumulates orphaned rows over time
- If a workspace with the same name is later recreated, old permission records "revive" — users who had permissions on the old workspace suddenly have permissions on the new one
- Cache entries for the deleted workspace persist until TTL expires
- `list_workspace_permissions()` returns permissions for non-existent workspaces

**Prevention:**
- **Add a workspace deletion cascade in the after_request hook** (or in the proxy router's delete endpoint): after successful deletion from MLflow, delete all rows from `workspace_permissions` and `workspace_group_permissions` where `workspace = deleted_name`.
- **Also delete regex workspace permission records** that only match the deleted workspace (though this is harder to determine — regex rules may match multiple workspaces).
- **Flush workspace cache on workspace deletion** — not just invalidate a single entry, since the deletion affects all users.
- **Check for orphaned permissions** in a startup health check or admin endpoint.
- **The "no resources" check before deletion** should be comprehensive: check experiments, models, prompts, scorers, etc. scoped to the workspace. This is potentially expensive — consider an async check or a dedicated endpoint.

**Detection:**
- `SELECT * FROM workspace_permissions WHERE workspace NOT IN (list of active workspaces)` returns rows
- Users report having permissions on workspaces that don't exist
- Permission management UI shows workspaces in the list that can't be navigated to

**Phase to address:** Workspace CRUD backend phase — the deletion cascade must be implemented alongside the delete proxy.

---

### Pitfall 10: Regex Workspace Permission Resolution Order — Where in the Chain?

**What goes wrong:**
The current `_lookup_workspace_permission` checks: user-level → group-level → return None. Adding regex means deciding where regex fits in this chain and whether it follows `PERMISSION_SOURCE_ORDER` from config.

The resource-level permission resolution uses `PERMISSION_SOURCE_ORDER` (default: `["user", "group", "regex", "group-regex"]`) via `get_permission_from_store_or_default()`. Workspace permissions currently bypass this mechanism — they use a hardcoded order in `_lookup_workspace_permission`. This inconsistency means:

1. An admin configures `PERMISSION_SOURCE_ORDER = ["regex", "user", "group", "group-regex"]` expecting regex to take priority for workspace permissions too, but it doesn't.
2. Regex workspace permissions are checked AFTER user-level permissions, so a user with explicit READ on a workspace can't be overridden by a regex rule granting MANAGE.

**Why it happens:**
Workspace permissions were implemented as standalone (per decision WSAUTH-B) with their own lookup chain, separate from the generic `resolve_permission()` function. Adding regex means either extending this standalone chain or integrating it with the generic resolution mechanism.

**Prevention:**
- **Follow `PERMISSION_SOURCE_ORDER` for workspace permissions too.** Add "regex" and "group-regex" sources to `_lookup_workspace_permission` in the same order as configured. This ensures consistent behavior across resource and workspace permissions.
- Alternatively, **if workspace permissions intentionally bypass `PERMISSION_SOURCE_ORDER`**, document this clearly and explain why (e.g., "workspace is a tenant boundary, not a resource — explicit user/group grants always take priority over regex patterns").
- **Whichever approach is chosen, test these edge cases**:
  - User has explicit READ, regex grants MANAGE → what wins?
  - User has no explicit permission, group grants READ, regex grants MANAGE → what wins?
  - User is in two groups with conflicting workspace permissions → highest wins (existing behavior)

**Detection:**
- Admin sets a regex workspace permission but it never takes effect because user-level permission always wins
- Permission resolution for workspaces produces different results than expected based on `PERMISSION_SOURCE_ORDER` config
- Inconsistent behavior between resource permissions (which follow the config order) and workspace permissions (which don't)

**Phase to address:** Regex workspace permissions phase — the resolution order design must be decided before implementation.

---

## Minor Pitfalls

### Pitfall 11: Frontend Workspace Picker — Admin vs Non-Admin Workspace Lists

**What goes wrong:**
Admins see ALL workspaces (bypass filtering in `_filter_list_workspaces`). Non-admins see only workspaces they have permissions for. The workspace picker dropdown must handle both cases. If the picker calls the same `ListWorkspaces` API for both user types, the experience differs: admin sees 100 workspaces, non-admin sees 3.

For non-admins, the picker list may not include the workspace they're trying to access (e.g., they were just granted access but the picker list is cached). For admins, a long dropdown of 100+ workspaces is unwieldy.

**Prevention:**
- For admins: add search/filter to the workspace picker dropdown when >10 workspaces.
- For non-admins: the picker list IS the user's accessible workspaces — if a workspace isn't in the list, they can't access it (by design).
- Add a "refresh" action to the picker that re-fetches the workspace list.
- Cache the workspace list in the frontend with a short TTL (30-60s), not indefinitely.

**Phase to address:** Global workspace picker UI phase.

---

### Pitfall 12: MLflow Workspace API Instability — PUBLIC_UNDOCUMENTED

**What goes wrong:**
The upstream workspace API (`/api/3.0/mlflow/workspaces`) is `PUBLIC_UNDOCUMENTED`. This means:
- Response format may change in minor releases without notice
- Endpoints may be renamed or removed
- New required fields may be added to request bodies
- Error codes may change

The proxy hardcodes assumptions about the API shape.

**Prevention:**
- **Abstract the MLflow workspace API behind an interface.** Don't sprinkle `httpx.post('/api/3.0/mlflow/workspaces', json={...})` throughout the codebase — create a `MlflowWorkspaceClient` class that encapsulates all API calls.
- **Pin the expected MLflow version range** in the compatibility notes.
- **Add integration tests** that actually call MLflow's workspace API (not mocked) to detect breakage early.
- **Use defensive parsing**: don't crash if the response has unexpected fields, just ignore them.
- **Monitor MLflow release notes** for workspace API changes.

**Phase to address:** Workspace CRUD backend phase — design the proxy as an abstraction layer.

---

### Pitfall 13: Workspace Picker Header State vs URL State Mismatch

**What goes wrong:**
The workspace picker stores the selected workspace in React state/context. But admin pages may have workspace-specific URLs (e.g., `/workspaces/prod/users`). If the user navigates to a workspace detail page via URL bookmark but the picker shows a different workspace, the page content and the picker are out of sync.

**Prevention:**
- The workspace detail pages should NOT be affected by the global picker — they show the workspace from the URL parameter.
- The global picker affects list/search pages (experiments, models) that don't have a workspace in the URL.
- OR: the workspace picker and URL are always in sync — navigating to a workspace detail page updates the picker, and changing the picker navigates to the selected workspace's page.
- Choose one pattern and be consistent.

**Phase to address:** Global workspace picker UI phase.

---

### Pitfall 14: cachetools Not Pinned — Transitive Dependency Risk

**What goes wrong:**
The existing `.planning/PROJECT.md` already flags: "`cachetools` is transitive dependency only (via MLflow) — not pinned in pyproject.toml." The workspace permission cache uses `TTLCache` from cachetools. If a future MLflow version drops cachetools or changes the version, the plugin breaks at import time.

**Prevention:**
- Add `cachetools>=5,<7` as a direct dependency in `pyproject.toml`.
- This is a one-line change but prevents a cryptic import error in production.

**Phase to address:** Any phase — quick fix that should be done immediately.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Workspace CRUD proxy backend | Proxy error conflation (P1), permission escalation (P2), deletion cascade (P9), API instability (P12) | Parse MLflow errors, separate workspace MANAGE from workspace lifecycle MANAGE, add cascade delete, abstract the API client |
| Workspace management admin UI | Name validation mismatch (P6), admin vs non-admin lists (P11) | Validate in proxy AND handle MLflow errors, adapt dropdown for different user roles |
| Global workspace picker | State management (P7), header vs URL mismatch (P13) | React Context + localStorage, choose sync strategy and be consistent |
| Workspace-scoped search filtering | Performance death spiral (P3), hook ordering (P8), feature flag bypass (P5) | Filter workspace FIRST, modify existing functions, gate on feature flag |
| Regex workspace permissions | Cache invalidation gaps (P4), resolution order (P10), feature flag bypass (P5) | Flush entire cache on regex CUD, follow PERMISSION_SOURCE_ORDER, gate at router level |

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces for this milestone.

- [ ] **Workspace CRUD proxy**: Often missing error response normalization — verify MLflow error codes are mapped to proper HTTP status codes and user-facing messages
- [ ] **Delete workspace check**: Often missing comprehensive resource check — verify experiments, models, prompts, scorers, gateway resources are all checked before allowing deletion
- [ ] **Search filtering**: Often missing workspace filter for logged models and scorers — verify `_filter_search_logged_models` also applies workspace scoping, not just experiments and models
- [ ] **Regex workspace permissions**: Often missing cache flush — verify `flush_workspace_cache()` is called from regex permission CUD endpoints
- [ ] **Regex workspace permissions in lookup chain**: Often missing integration with `_lookup_workspace_permission` — verify regex and group-regex are added as resolution steps
- [ ] **Workspace picker header injection**: Often missing `X-MLFLOW-WORKSPACE` header — verify ALL HTTP client calls include the workspace header from the picker context
- [ ] **Feature flag gating for new routers**: Often missing conditional registration — verify workspace CRUD and regex permission routers are not registered when `MLFLOW_ENABLE_WORKSPACES=false`
- [ ] **Workspace rename permission cascade**: Often missing — verify that if workspace rename is supported, all `workspace_permissions` and `workspace_group_permissions` rows are updated with the new name
- [ ] **GraphQL workspace filtering**: Often forgotten — verify that GraphQL queries also respect workspace scoping
- [ ] **Frontend runtime config includes workspace flag**: Often missing — verify `config.json` endpoint returns `workspacesEnabled` so the frontend can hide/show workspace UI elements

## Recovery Strategies

When pitfalls occur despite prevention.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Proxy error conflation (users see 500s) | LOW | Add error mapping layer to proxy. Redeploy. No data loss. |
| Permission escalation via MANAGE | MEDIUM | Audit workspace mutation logs. Revert unauthorized changes. Restrict MANAGE → admin-only for workspace CRUD. |
| Search performance death spiral | MEDIUM | Add re-fetch iteration cap immediately. Profile and optimize. May need DB-side workspace mapping table. |
| TTLCache stale after regex change | LOW | Add `flush_workspace_cache()` call. Reduce TTL as interim fix. |
| Feature flag bypass | LOW | Add conditional router registration. Redeploy. Clean up any workspace records created in non-workspace deployments. |
| Orphaned workspace permissions | LOW | Run cleanup query: `DELETE FROM workspace_permissions WHERE workspace NOT IN (active_workspaces)`. |
| Workspace picker state lost on navigation | LOW | Add localStorage persistence. Verify React Context wraps all routes. |
| MLflow API change breaks proxy | MEDIUM | Pin MLflow version. Update proxy to handle new API shape. Abstraction layer limits blast radius. |

## Sources

- Direct codebase analysis (v1.0 post-merge state):
  - `hooks/after_request.py` — existing search filtering, workspace list filtering, cascade delete patterns
  - `hooks/before_request.py` — workspace validators, creation gating, permission handler registration
  - `validators/workspace.py` — current admin-only authorization for workspace CRUD
  - `utils/workspace_cache.py` — TTLCache implementation, invalidation patterns, lookup chain
  - `utils/permissions.py` — permission resolution registry, workspace fallback, can_* helpers
  - `dependencies.py` — FastAPI dependency injection for workspace manage/read checks
  - `middleware/auth_middleware.py` — AuthContext creation, workspace header extraction
  - `bridge/user.py` — AuthContext retrieval in Flask context
  - `repository/_base.py` — generic repository patterns (regex, group-regex base classes)
  - `repository/workspace_permission.py` — standalone workspace permission CRUD
  - `db/models/workspace.py` — ORM models, composite PK design
  - `config.py` — feature flags, cache configuration
  - `routers/workspace_permissions.py` — existing workspace permission CRUD endpoints
  - `web-react/src/core/services/http.ts` — HTTP client, header handling
  - `web-react/src/shared/components/header.tsx` — header component structure
- `.planning/PROJECT.md` — milestone scope, constraints, known gaps (cachetools, PUBLIC_UNDOCUMENTED API)
- Prior pitfalls research (v1.0) — pitfall continuity for cross-tenant filtering, feature flag gating
- MLflow workspace API status: `PUBLIC_UNDOCUMENTED` per v3.0 protobuf annotations (MEDIUM confidence — based on code inspection, not official MLflow docs)

---
*Pitfalls research for: v1.1 Workspace Management — CRUD proxy, search filtering, regex permissions, global workspace picker*
*Researched: 2026-03-24*
