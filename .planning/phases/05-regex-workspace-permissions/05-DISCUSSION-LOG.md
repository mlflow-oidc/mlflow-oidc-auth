# Phase 5: Regex Workspace Permissions - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-24
**Phase:** 05-regex-workspace-permissions
**Areas discussed:** Router organization, Cache resolution order, Priority field design, Cache flush scope

---

## Router Organization

| Option | Description | Selected |
|--------|-------------|----------|
| Separate router (Recommended) | Follow the established pattern — every other resource type puts regex endpoints in a separate file. Keeps files focused and consistent. Would create workspace_regex_permissions.py alongside workspace_permissions.py. | ✓ |
| Same router | Add regex endpoints to the existing workspace_permissions.py. Less files, but breaks the pattern every other resource type follows. The file would grow from ~120 lines to ~250+. | |
| You decide | Let the planner decide based on implementation size and file organization. | |

**User's choice:** Separate router (Recommended)
**Notes:** Consistent with all 7 other resource types.

### Follow-up: URL Prefix

| Option | Description | Selected |
|--------|-------------|----------|
| /workspace/permissions/regex/ (Recommended) | e.g., /api/2.0/mlflow/workspace/permissions/regex/user and .../regex/group. Follows existing pattern where other regex endpoints nest under their resource's permission path. | ✓ |
| Flat top-level path | e.g., /api/2.0/mlflow/workspace-regex-permissions/user. Flatter, but diverges from how other resource regex endpoints are structured. | |
| You decide | Let the planner decide the URL structure. | |

**User's choice:** /workspace/permissions/regex/ (Recommended)

---

## Cache Resolution Order

| Option | Description | Selected |
|--------|-------------|----------|
| Direct before regex (Recommended) | user-direct → group-direct → user-regex → group-regex. Direct permissions take precedence over pattern-matched ones. Consistent with PERMISSION_SOURCE_ORDER for other resources. | |
| User sources before group sources | user-direct → user-regex → group-direct → group-regex. User sources (both direct and regex) take precedence over group sources. Prioritizes user-level specificity. | ✓ |
| Highest permission wins | Check all 4 sources and return the highest permission level found. No short-circuit. Always returns the most permissive match. | |

**User's choice:** User sources before group sources
**Notes:** Prioritizes user-level specificity over group-level.

### Follow-up: Short-circuit Behavior

| Option | Description | Selected |
|--------|-------------|----------|
| First match wins (Recommended) | Once a matching source is found, return immediately. First match wins. This is how the current workspace cache works. | ✓ |
| Check all, return highest | Check all 4 sources and return the highest permission found across all matches. More permissive, but more expensive. | |

**User's choice:** First match wins (Recommended)

### Follow-up: Configurability

| Option | Description | Selected |
|--------|-------------|----------|
| Hardcoded order (Recommended) | Hardcode user-direct → user-regex → group-direct → group-regex. Simple and predictable. | |
| Use PERMISSION_SOURCE_ORDER config | Respect PERMISSION_SOURCE_ORDER config for workspace resolution too. More flexible but adds complexity. | ✓ |

**User's choice:** Use PERMISSION_SOURCE_ORDER config

---

## Priority Field Design

| Option | Description | Selected |
|--------|-------------|----------|
| No priority field (Recommended) | Keep workspace regex consistent with all 7 other resource types. When multiple regexes match, use highest permission. Simpler, consistent. | |
| Add priority field | Add integer priority column. Lower number = higher priority. First matching regex by priority wins. Gives admins fine-grained control over overlapping patterns. | ✓ |
| Optional priority, highest fallback | Add priority field but make it optional (default 0). If all priorities equal, fall back to highest-permission-wins. | |

**User's choice:** Add priority field
**Notes:** Diverges from other resource types' regex models. This is a deliberate choice for workspace permissions.

### Follow-up: Sort Direction

| Option | Description | Selected |
|--------|-------------|----------|
| Lower number = higher priority (Recommended) | Priority 1 wins over priority 10. Common pattern in firewall rules, route matching. | ✓ |
| Higher number = higher priority | Priority 10 wins over priority 1. Higher number means more important. | |

**User's choice:** Lower number = higher priority (Recommended)

### Follow-up: Tie-break

| Option | Description | Selected |
|--------|-------------|----------|
| Highest permission wins (Recommended) | When two regexes match at same priority, return most permissive. Safe fallback. | ✓ |
| Lowest permission wins | When two regexes match at same priority, return least permissive. Safer from security standpoint. | |
| Unique priority constraint | Disallow duplicate priorities. No ties to break. | |

**User's choice:** Highest permission wins (Recommended)

---

## Cache Flush Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Full cache clear on regex CUD (Recommended) | Call cache.clear() when any regex permission is created/updated/deleted. Direct permission CUD continues using selective eviction. | ✓ |
| Pattern-aware selective eviction | On regex CUD, iterate cached keys, check which match the changed regex, evict those. More surgical but complex. | |
| Full clear on any CUD | Full cache clear on ALL permission CUD (regex AND direct). One strategy for everything. | |

**User's choice:** Full cache clear on regex CUD (Recommended)

### Follow-up: cachetools Dependency

| Option | Description | Selected |
|--------|-------------|----------|
| Pin as direct dep (Recommended) | Add cachetools>=5.5.0 to pyproject.toml. Currently only transitive via google-auth. | ✓ |
| Keep as transitive only | Keep relying on transitive dependency. Fragile. | |

**User's choice:** Pin as direct dep (Recommended)

---

## Agent's Discretion

- Alembic migration implementation details
- Pydantic request/response model structure
- Internal store method organization
- Test structure and coverage strategy
- Feature flag gating implementation

## Deferred Ideas

None — discussion stayed within phase scope.
