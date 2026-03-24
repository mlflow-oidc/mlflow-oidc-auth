# Phase 5: Regex Workspace Permissions - Context

**Gathered:** 2026-03-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Admins can define pattern-based workspace access rules (user-regex and group-regex) that automatically grant permissions to matching workspaces. Includes DB models, entities, repositories, store methods, router endpoints, cache integration with configurable resolution order, and Alembic migration. No UI work — admin UI is Phase 8.

</domain>

<decisions>
## Implementation Decisions

### Router Organization
- **D-01:** Separate router file (`workspace_regex_permissions.py`), not added to existing `workspace_permissions.py`. Consistent with all 7 other resource types that each have dedicated regex routers.
- **D-02:** URL prefix: `/api/2.0/mlflow/workspace/permissions/regex/user` and `.../regex/group`. Follows existing pattern where regex endpoints nest under their resource's permission path.

### Cache Resolution Order
- **D-03:** Resolution order: user-direct → user-regex → group-direct → group-regex. User-level sources (both direct and regex) take precedence over group-level sources.
- **D-04:** First match wins (short-circuit). Once a matching source is found, return immediately — do not check remaining sources for a higher permission.
- **D-05:** Resolution order respects `PERMISSION_SOURCE_ORDER` config, not hardcoded. Workspace cache must parse and apply the configured order.

### Priority Field Design
- **D-06:** Add integer `priority` column to workspace regex permission tables. This is NEW — existing regex models for other resource types do not have a priority field.
- **D-07:** Lower number = higher priority (firewall-rule convention). Priority 1 wins over priority 10.
- **D-08:** Tie-break: when multiple regex patterns match at the same priority, return the highest permission level (most permissive). Safe fallback — doesn't silently deny access.

### Cache Flush Scope
- **D-09:** Full `cache.clear()` on the TTLCache when any regex permission is created/updated/deleted. Direct permission CUD continues using existing selective key eviction.
- **D-10:** Pin `cachetools>=5.5.0` as a direct dependency in `pyproject.toml`. Currently only a transitive dependency via google-auth.

### Agent's Discretion
- Exact Alembic migration implementation details (column types, indexes, constraints)
- Pydantic request/response model structure for the new endpoints
- Internal organization of store methods (delegation to repository classes)
- Test structure and coverage strategy
- Feature flag gating implementation for the new router (carried forward: must not register when `MLFLOW_ENABLE_WORKSPACES=false`)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & Roadmap
- `.planning/REQUIREMENTS.md` — WSREG-01 through WSREG-07: full acceptance criteria for regex workspace permissions
- `.planning/ROADMAP.md` — Phase 5 definition, success criteria, dependency on Phase 4

### Research
- `.planning/research/STACK.md` — Zero new libraries needed, pin cachetools>=5.5.0 as direct dependency
- `.planning/research/FEATURES.md` — TS-05 regex workspace permissions spec
- `.planning/research/ARCHITECTURE.md` — Integration patterns for workspace permission resolution
- `.planning/research/PITFALLS.md` — P4 TTLCache invalidation strategy, P10 resolution order concerns

### Existing Patterns (code references)
- `mlflow_oidc_auth/repository/_base.py` — `BaseRegexPermissionRepository` and `BaseGroupRegexPermissionRepository` base classes with full CRUD
- `mlflow_oidc_auth/repository/experiment_permission_regex.py` — Example regex repo (~18 lines, extends base). Pattern to follow.
- `mlflow_oidc_auth/repository/experiment_permission_regex_group.py` — Example group regex repo (~18 lines). Pattern to follow.
- `mlflow_oidc_auth/utils/workspace_cache.py` — `_lookup_workspace_permission()` is the integration point; `invalidate_workspace_permission()` for cache flush
- `mlflow_oidc_auth/utils/permissions.py` — `PERMISSION_REGISTRY`, `_match_regex_permission()` for reuse, `PERMISSION_SOURCE_ORDER` config pattern
- `mlflow_oidc_auth/db/models/workspace.py` — Existing `SqlWorkspacePermission`, `SqlWorkspaceGroupPermission` models. New regex models go here or in adjacent file.
- `mlflow_oidc_auth/entities/workspace.py` — Existing `WorkspacePermission`, `WorkspaceGroupPermission` entity classes. New regex entities follow same pattern.
- `mlflow_oidc_auth/routers/workspace_permissions.py` — Existing workspace permission router. New regex router is a sibling file.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `BaseRegexPermissionRepository` / `BaseGroupRegexPermissionRepository`: Full CRUD base classes — new repos extend these with `model_class` set and optionally add backward-compat aliases
- `_match_regex_permission()` in `utils/permissions.py`: Generic regex matcher used by all 7 resource types — reusable for workspace regex resolution (but will need priority-aware variant)
- `TTLCache` infrastructure in `workspace_cache.py`: Cache already set up, just needs new source lookups added

### Established Patterns
- Regex repos are trivial (~18 lines): extend base, set `model_class`, done
- DB models use auto-increment `id` PK with `(regex, user_id)` or `(regex, group_id)` columns for regex variants
- Entity classes are standalone (not extending a common base) — workspace entities follow this pattern
- All routers register via `create_app()` with feature flag gating

### Integration Points
- `_lookup_workspace_permission()` in `workspace_cache.py`: Add user-regex and group-regex as sources 3 and 4 (after user-direct and before/after group-direct per PERMISSION_SOURCE_ORDER)
- `invalidate_workspace_permission()`: Add `cache.clear()` call for regex CUD operations
- `SqlAlchemyStore` / `store.py`: New store methods delegating to new regex repository classes
- `create_app()` in `app.py`: Register new regex router with feature flag guard

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches. The priority field (D-06 through D-08) is the main novel element; everything else follows established patterns closely.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 05-regex-workspace-permissions*
*Context gathered: 2026-03-24*
