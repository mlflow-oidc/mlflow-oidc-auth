# Pitfalls Research

**Domain:** Multi-tenant organization support for MLflow OIDC auth plugin
**Researched:** 2026-03-23
**Confidence:** HIGH — based on direct codebase analysis, established multi-tenancy patterns, and known OIDC provider behavior

## Critical Pitfalls

### Pitfall 1: Cross-Tenant Data Leakage via Permission Resolution Fallback

**What goes wrong:**
The current permission resolution chain (`get_permission_from_store_or_default` in `utils/permissions.py:422-466`) falls back to `config.DEFAULT_MLFLOW_PERMISSION` when no explicit permission is found. Today the default is `MANAGE`. When orgs are added, a user in Org-A who has no explicit permission for an Org-B experiment would fall through all four resolution steps (user → group → regex → group-regex) and land on the **default permission** — which grants full access to a resource they should never see.

**Why it happens:**
The current system assumes a flat namespace: if you have no explicit permission, you get the default. There's no concept of "this resource belongs to a different org, so you don't even get to the fallback." The fallback is a safety net for a single-tenant world; in multi-tenant, it becomes a data leak.

**How to avoid:**
- Add an **org boundary check as the first step** in permission resolution, before user/group/regex/group-regex. If the resource's org doesn't match the user's org, return `NO_PERMISSIONS` immediately — never reach the fallback.
- Change the fallback behavior for multi-tenant mode: default should be `NO_PERMISSIONS` or configurable per-org.
- The org check must be a hard deny, not just another link in the chain — it should short-circuit, not participate in priority ordering.

**Warning signs:**
- Any permission resolution path that doesn't check org membership before checking resource permissions.
- Tests that verify cross-org access and find that users can read/manage resources in other orgs when no explicit permission exists.
- `DEFAULT_MLFLOW_PERMISSION = "MANAGE"` remaining as the global default after org support is added.

**Phase to address:**
Core org model/permission phase — this must be solved in the very first implementation phase, before any org-scoped resources exist. It's the foundational security invariant.

---

### Pitfall 2: Post-Fetch Search Filtering Leaks Cross-Org Metadata

**What goes wrong:**
The `after_request.py` hooks (`_filter_search_experiments`, `_filter_search_registered_models`, `_filter_search_logged_models`) fetch ALL results from MLflow's tracking store first, then filter by permission. With org support, these functions would initially return cross-org resources in the unfiltered response. Even if filtering removes them before the client sees results, the **pagination math breaks**: `max_results` accounting is wrong because it counts org-foreign resources, and the re-fetch loop (lines 86-106 of `after_request.py`) uses MLflow's store which has no org awareness.

More critically, if the org boundary check is implemented only in the filter step (after MLflow returns data), there's a timing window where cross-org data exists in server memory. For sensitive ML models, even transient exposure is a concern.

**Why it happens:**
MLflow's core tracking store has no permission/org-aware query interface. The plugin can only filter results post-fetch. This was acceptable for single-tenant (just hiding experiments you can't read), but in multi-tenant it means Org-B's experiment names, IDs, and metadata briefly exist in Org-A's request processing pipeline.

**How to avoid:**
- Add org-scoping to the filter functions explicitly: check org membership **before** iterating individual permissions. Filter out org-foreign resources first, then apply permission checks on the remainder.
- If MLflow 3.10 adds org-aware query parameters to the tracking store, use them to pre-filter at the query level.
- Never rely solely on post-fetch filtering for org isolation. If MLflow's store returns cross-org data, the filter must be fail-safe (deny if org can't be determined).

**Warning signs:**
- Search result counts that don't add up (user sees fewer results than `max_results` despite more existing).
- Performance degradation in search endpoints for orgs with few resources but sharing an instance with orgs that have many.
- Pagination tokens that skip entries unpredictably.

**Phase to address:**
Permission resolution update phase — immediately after the core org model. Must be implemented before the system is exposed to real multi-tenant traffic.

---

### Pitfall 3: Migration Breaks Existing Permissions — The "Null Org" Problem

**What goes wrong:**
Existing deployments have users, groups, and permissions with no org association. Adding an `org_id` column to permission tables creates a migration dilemma: if `org_id` is `NOT NULL`, existing rows fail. If `org_id` is `NULL`, code that filters by org will miss all pre-existing permissions (SQL `WHERE org_id = X` doesn't match `NULL`). Users who had working permissions suddenly lose all access.

**Why it happens:**
This is the classic "adding a required dimension to existing data" problem. The migration must handle the transition state where some data has no org, but the system needs org-aware queries.

**How to avoid:**
- Use a **sentinel "default org"** approach: the migration creates a default org and assigns all existing users, groups, and permissions to it. This preserves all existing access patterns.
- The default org should be configurable per deployment (admin names it during upgrade).
- Make org_id `NOT NULL` with a FK constraint after the migration populates all rows. Never leave it nullable in the final schema — nullable org_id invites bugs where new records are created without an org.
- Migration must be idempotent (safe to re-run) and must not require downtime. Alembic already runs on startup (`create_app()`), so the migration runs before the app serves traffic.

**Warning signs:**
- `SELECT * FROM experiment_permissions WHERE org_id IS NULL` returns rows after migration — means some records weren't assigned.
- Users report "permission denied" on resources they could access before the upgrade.
- SQL queries that use `= :org_id` instead of `IS NOT DISTINCT FROM :org_id` for the transition period.

**Phase to address:**
Database migration phase — must be a dedicated, carefully designed migration with rollback capability. Should include a pre-migration validation script that operators can run to preview the impact.

---

### Pitfall 4: OIDC Provider Org Claim Inconsistency

**What goes wrong:**
Different OIDC providers encode organization membership differently in their token claims. The code currently extracts groups via `userinfo.get(config.OIDC_GROUPS_ATTRIBUTE, [])` (auth.py:414) or a plugin. For orgs, developers might assume a similar `org` or `organization` claim exists. It often doesn't — or it varies wildly:
- **Keycloak**: Organizations are a recent feature (25+), exposed as custom claims configurable per realm. May appear in `organizations` claim or require custom mapper.
- **Okta**: Orgs map to `org_id` in token, but only with Okta Organizations feature enabled (enterprise tier).
- **Azure AD/Entra ID**: Tenant ID in `tid` claim; multi-tenant apps get it automatically but it's the Azure tenant, not a business org.
- **Auth0**: Organizations send `org_id` and `org_name` claims, but only when the login prompt specifies the org.
- **Google**: No org claim at all. Workspace domain is in `hd` claim.
- **GitLab**: No native org claim; groups are the closest.

**Why it happens:**
There's no OIDC standard claim for "organization." It's entirely provider-specific. Developers test with one provider and assume it generalizes.

**How to avoid:**
- **Never hard-code a single claim path.** Use a configurable `OIDC_ORG_ATTRIBUTE` setting (similar to existing `OIDC_GROUPS_ATTRIBUTE`).
- Support the **group detection plugin pattern** already in the codebase (`OIDC_GROUP_DETECTION_PLUGIN` in `config.py:87`) — add an equivalent `OIDC_ORG_DETECTION_PLUGIN` for providers that need custom logic to extract org membership.
- Provide a **hybrid mode**: org can come from OIDC claims (automatic) OR be admin-assigned (manual). Some providers simply cannot provide org claims.
- Document the claim shape expected: is it a string? A list? An object with `id` and `name`? Different providers return different shapes.

**Warning signs:**
- Org detection works with the developer's OIDC provider but fails in CI or when users test with a different provider.
- Silently empty org claim (claim exists but is an empty string or empty list) — code must distinguish "no org claim configured" from "user has no org."
- Token refresh losing the org claim (some providers only include org in ID token, not access token).

**Phase to address:**
OIDC integration phase — build alongside the org model, but plan for iterative provider support. Start with configurable claim + plugin hook; don't try to support every provider natively.

---

### Pitfall 5: Permission Resolution Complexity Explosion (8→40+ Functions)

**What goes wrong:**
The current codebase already has ~8 nearly identical permission resolution functions in `utils/permissions.py` (466 lines), one per resource type. Each has 4 variants (user, group, regex, group-regex). Adding an org dimension would mean every function needs an org-scoped variant or an org parameter threaded through. With 7 resource types × 4 permission variants × org scoping = 28+ code paths, plus org-level permissions themselves (org-admin, org-member roles). The CONCERNS.md already identifies this as tech debt.

Without refactoring first, adding org support means:
- 7 new `_permission_*_sources_config` functions (or modifying all existing ones)
- 7+ new org-specific permission check functions
- All 26+ repository classes need org-aware variants
- All permission routers (2390 + 2205 lines) need org endpoints

**Why it happens:**
The current architecture uses copy-paste-modify rather than generic abstractions. Each new dimension multiplies the existing duplication.

**How to avoid:**
- **Refactor BEFORE adding org support.** Create a generic `resolve_permission(resource_type, resource_id, username, org_id)` function that all resource types use (the fix suggested in CONCERNS.md).
- Build a generic repository base class for permissions, parameterized by resource type and org scope.
- Use the router factory pattern suggested in CONCERNS.md before adding org-scoped endpoints.
- If refactoring first isn't possible, at least add the org parameter to the existing resolution chain as a single injection point rather than duplicating all functions.

**Warning signs:**
- PR adding org support touches more than 20 files with similar changes to each.
- `utils/permissions.py` grows beyond 600 lines.
- New bugs where org check was added to one resource type but missed in another.
- Code review reveals inconsistent org handling between resource types.

**Phase to address:**
**Must be a pre-requisite phase** before org implementation. The existing tech debt (identified in CONCERNS.md) should be addressed in a refactoring phase to create generic permission abstractions. Without this, org support is unmaintainable.

---

### Pitfall 6: MLflow Plugin Boundary Violations — Trying to Control What You Can't

**What goes wrong:**
The auth plugin intercepts MLflow's Flask endpoints via `before_request`/`after_request` hooks. It cannot control:
- **MLflow's internal data storage** — experiments, models, runs are stored by MLflow's tracking store, which has no org concept. The plugin can only filter access, not partition storage.
- **Artifact storage** — artifacts are stored in configured backends (S3, Azure Blob, etc.) that MLflow manages. The plugin can't enforce per-org artifact isolation at the storage level.
- **MLflow UI** — the hack.py HTML injection is fragile and can't add org context/switching to MLflow's built-in UI.
- **GraphQL queries** — the monkey-patch on `_get_graphql_auth_middleware` (a private API) limits what the plugin can do with GraphQL responses.

Developers might try to implement org-level artifact isolation, per-org tracking stores, or deep MLflow UI integration, which are all outside the plugin's boundary.

**Why it happens:**
The line between "auth plugin can control access" and "auth plugin can control data placement" is blurry. Org support in other products usually includes data isolation, not just access control. Developers assume the plugin can do both.

**How to avoid:**
- **Document the plugin boundary explicitly** in design docs: the plugin controls WHO can access WHAT, not WHERE data lives.
- Org support in this plugin = access control + visibility filtering. NOT storage partitioning.
- Don't try to make experiments/models "belong to" orgs at the MLflow storage level — that's MLflow core's job. Instead, maintain an org-resource mapping table in the auth plugin's own database.
- If MLflow 3.10 adds org-aware APIs, use them. If not, the plugin maintains its own mapping.
- Artifact isolation is an infrastructure concern (separate S3 buckets per org) — document this as out of scope for the auth plugin.

**Warning signs:**
- Design doc mentions modifying MLflow's tracking store configuration per org.
- Code tries to set different `MLFLOW_ARTIFACT_ROOT` per request/org.
- Feature requests for "org-specific MLflow settings" landing on the auth plugin.

**Phase to address:**
Design/architecture phase — establish the boundary before implementation begins. The PROJECT.md already lists "Org-specific MLflow configuration" as out of scope, but this needs to be reiterated in the org design doc.

---

### Pitfall 7: Bridge Layer Doesn't Carry Org Context

**What goes wrong:**
The ASGI-to-WSGI bridge currently passes exactly two values: `username` and `is_admin` (via `mlflow_oidc_auth.username` and `mlflow_oidc_auth.is_admin` in WSGI environ). Adding org support requires the org context to flow from FastAPI auth middleware → ASGI scope → WSGI environ → Flask hooks → validators. If the bridge isn't updated, Flask-side validators have no org context to check against.

The bridge is identified as fragile in CONCERNS.md: "environ keys are modified, auth breaks silently." Adding a new key (`mlflow_oidc_auth.org_id`) touches `AuthMiddleware.dispatch()`, `AuthInjectingWSGIApp.__call__()`, and `bridge/user.py` — and there are no integration tests for the bridge.

**Why it happens:**
The bridge was designed for a simple (username, is_admin) tuple. Adding org context is a cross-cutting change that touches every layer.

**How to avoid:**
- Use a **typed context object** instead of individual environ keys. Replace the dict `{"username": ..., "is_admin": ...}` with a dataclass/TypedDict that includes `org_id`, `org_role`, etc. This makes it harder to forget a field.
- Add **assertions in the Flask bridge** that verify required context keys are present (fail-fast instead of silently missing org context).
- Add integration tests for the bridge BEFORE making changes. The test should verify that all context fields flow correctly from FastAPI → Flask.
- Use constants for environ key names (already suggested in CONCERNS.md but not implemented).

**Warning signs:**
- Validators that check `get_request_org()` but it returns `None` silently.
- Flask hooks that work for non-org requests but fail-open for org-scoped requests.
- Intermittent 500 errors where org context is missing in some request paths but not others.

**Phase to address:**
Early implementation phase — bridge update must happen before any org-aware validators are written. This is a foundation change.

---

### Pitfall 8: Group-to-Org Relationship Design — Flat vs Nested

**What goes wrong:**
There are three common designs, each with a trap:

1. **Groups scoped to orgs** (each group belongs to one org): Breaks existing groups that span orgs. Existing groups have no org_id, so they become orphans or get arbitrarily assigned.

2. **Groups independent of orgs** (many-to-many): Creates confusion about what "group permission" means in an org context. A user in Group-X and Org-A with a group-level experiment permission — does that permission apply if the experiment is in Org-B? If yes, groups become a cross-org backdoor. If no, the group permission is silently ignored, confusing admins.

3. **Groups nested under orgs** (org → groups → users hierarchy): Most intuitive, but incompatible with the current flat group model where groups are synced from OIDC claims. OIDC providers send group lists, not org→group hierarchies.

**Why it happens:**
Groups and orgs serve overlapping purposes (organizing users with shared permissions), so the relationship between them is genuinely ambiguous. The wrong choice leads to either data leakage (groups bypass org boundaries) or broken workflows (groups become org-scoped but existing cross-org groups break).

**How to avoid:**
- **Decision: Groups remain independent, but permissions are org-scoped.** A group can exist in multiple orgs, but a group's permissions for Org-A resources don't grant access to Org-B resources. The org boundary is enforced at the permission level, not the group level.
- This means: `experiment_group_permissions` gets an `org_id` column, and permission resolution checks that the permission's org matches the resource's org.
- Existing groups continue to work in the default org. No structural change to groups themselves.
- Document clearly: "Groups are NOT security boundaries between orgs. Orgs are."

**Warning signs:**
- Design doc describes groups as "belonging to" an org (creates migration problems).
- A group admin in Org-A can grant permissions on Org-B resources via group membership.
- Users in multiple orgs have different group memberships per org, but the system can't express this.

**Phase to address:**
Design phase — this decision must be made before database schema design. It affects every permission table's schema.

---

### Pitfall 9: Admin Bypass Without Org Scoping

**What goes wrong:**
The current admin check is a simple boolean: `is_admin = True` bypasses ALL permission checks (see `before_request.py:357-358`). With orgs, "admin" needs scoping:
- **Global admin** (system-wide, can manage all orgs) — current behavior
- **Org admin** (can manage their org but not others)

If org-admin is implemented as the same `is_admin` flag, org-admins bypass all checks including cross-org boundaries. If it's a new concept, every admin check in the codebase must be updated to distinguish global-admin from org-admin.

**Why it happens:**
The admin bypass is deeply embedded: it's checked in `before_request_hook` (line 357), all `_filter_search_*` functions (first line), and implicitly in any code path that calls `get_fastapi_admin_status()`. Adding a new admin tier requires touching every one of these.

**How to avoid:**
- Introduce an **`OrgRole` enum**: `GLOBAL_ADMIN`, `ORG_ADMIN`, `MEMBER`. Store it in the user-org relationship, not on the user.
- Replace `is_admin` boolean checks with a function like `is_admin_for(org_id)` that checks both global admin and org-admin status.
- The bridge must carry org role, not just boolean admin status.
- **Global admin bypass stays unchanged** — it still skips all checks. Org-admin only bypasses checks for their own org's resources.

**Warning signs:**
- Org admin can access resources in another org.
- Code still uses bare `is_admin` checks without org context.
- `get_fastapi_admin_status()` returns a boolean and nothing else.

**Phase to address:**
Org model phase — must be designed alongside the org entity. The admin model is core to the org security model.

---

### Pitfall 10: Backward Compatibility — Deployments Without Orgs

**What goes wrong:**
Existing deployments have no orgs. After upgrading, the system must work identically to before for operators who don't want/need org support. Common failures:
- Config options that are required but have no default → crash on startup.
- API responses that now include `org_id: null` → break existing API clients parsing responses.
- Permission management UI that now requires org selection → breaks workflow for single-org deployments.
- OIDC callback that requires org claim → blocks login for providers without org claims.

**Why it happens:**
Multi-tenant features are designed for multi-tenant use cases. Single-tenant deployments are an afterthought.

**How to avoid:**
- **Implicit default org**: deployments without explicit org config operate with a single implicit org. All existing data migrated to this default org. The system behaves identically — no new config, no new UI steps, no new API fields required.
- Org features are opt-in: a feature flag or the presence of multiple orgs activates org-aware UI elements.
- API backward compatibility: `org_id` is optional in API requests; if omitted, defaults to the user's org or the default org.
- OIDC org claim is optional: if not configured, all users join the default org.
- The admin UI shows org management only when multiple orgs exist.

**Warning signs:**
- Upgrade requires new mandatory environment variables.
- Existing API scripts break after upgrade.
- Users can't log in after upgrade because org claim isn't configured.
- Default permission changes break existing access patterns.

**Phase to address:**
All phases — backward compatibility is a constraint on every change, not a phase. But it should be validated in a dedicated testing/migration phase with a "upgrade without any new config" test scenario.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Adding `org_id` as optional/nullable to existing tables instead of default org migration | Simpler migration, no data changes | Every query must handle NULL org, bugs where new records miss org_id | Never — always populate a default org |
| Hardcoding org claim to a specific OIDC provider's format | Fast to implement for one provider | Breaks when users deploy with different providers, support burden | Only in a prototype/spike, never in released code |
| Making org check a separate `if` in each validator instead of a generic interceptor | Works without refactoring | 30+ validators each need the same org check, inconsistency guaranteed | Never — invest in the generic pattern |
| Skipping the bridge update and passing org via a Flask `g` variable set in before_request | Avoids touching the middleware stack | `g` isn't available in all contexts, breaks for GraphQL and non-standard paths | Never — the bridge is the correct place |
| Copy-pasting permission resolution functions with org parameter | Fast to implement | Existing 466-line file becomes 900+ lines, maintenance nightmare | Only if refactoring is explicitly deferred to next milestone |

## Integration Gotchas

Common mistakes when connecting to external services.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| OIDC Provider (org claims) | Assuming `org_id` claim is always a string | Accept string, int, or object. Normalize on receipt. Store as string. |
| OIDC Provider (group + org) | Assuming groups and orgs come in the same token | Some providers put groups in ID token and org in access token (or userinfo). Check all three. |
| MLflow 3.10 org API | Assuming MLflow's org model matches what the plugin needs | MLflow may have a simpler org model (just namespacing). The auth plugin needs its own org-permission model that maps TO MLflow's model. |
| MLflow tracking store | Trying to add `WHERE org_id = X` to MLflow's internal queries | MLflow's store is not org-aware. The plugin must filter post-query or maintain its own resource-to-org mapping. |
| Database migrations (Alembic) | Running migration on production with large tables without batching | Alembic `op.add_column` with `NOT NULL` on a table with millions of rows locks the table. Use `batch_alter_table` or add nullable first, populate, then alter. |
| GraphQL (monkey-patch) | Assuming org context is available in the GraphQL auth middleware | The GraphQL patch uses a private MLflow function. Org context must be available via the same bridge mechanism. Verify it works. |

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Org check as additional DB query per request | p50 latency doubles; DB connection pool exhaustion | Cache user-org membership (TTL 30-60s); include org_id in auth context from middleware | >100 concurrent users, or any deployment with no permission caching (current state) |
| Post-fetch org filtering on search results | Pagination returns empty pages; users see "no experiments" when thousands exist in other orgs | Pre-filter by org where possible; adjust pagination math to account for filtered-out cross-org results | >1000 experiments across orgs, or orgs with very unequal resource counts |
| Loading all orgs + org permissions on user profile | `/users/list` endpoint becomes 10x slower (already identified as eagerly loading all permissions) | Lazy load org data; separate endpoint for org details | >50 users with >5 orgs each |
| Regex permission check across all orgs | `re.match()` on every regex permission for every org on every request | Scope regex permissions to org before pattern matching; only load regex patterns for the user's current org | >100 regex permission rules |
| Org membership validation on every request via DB | No caching means every request triggers `SELECT ... FROM user_orgs WHERE user_id = X` | Embed org membership in JWT claims or session; validate against DB only on login/refresh | >50 rps |

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Org boundary enforced only in UI, not API | API clients bypass org isolation entirely; data exfiltration via direct API calls | Enforce org boundary in Flask before_request hooks and FastAPI routers, not just frontend |
| Org admin can promote to global admin | Privilege escalation: org admin creates a global admin account | Org admin role is strictly lower than global admin; only global admins can create global admins |
| Resource IDs are globally unique (not org-scoped) | User guesses experiment ID from another org and accesses it via direct API call | Org check on every resource access, even when the user provides the resource ID directly |
| Org switching without re-authentication | Session carries old org context after switching; stale permissions used | Clear permission cache on org switch; re-validate org membership from token/DB |
| Default org has weaker isolation than named orgs | Attack: keep resources in "default" org to avoid isolation rules | Default org has identical isolation rules; it's just unnamed, not unprotected |
| Gateway validators fail-open (existing bug) extended to org context | If gateway resource name can't be resolved AND org can't be determined, validator returns True | Fix existing fail-open bug (CONCERNS.md identifies this) BEFORE adding org support; ensure org check also fails closed |

## UX Pitfalls

Common user experience mistakes in this domain.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Requiring org selection on every action | Users in single-org deployments see meaningless "Select org" dropdown | Auto-select when user has one org; show selector only for multi-org users |
| Showing all orgs a user belongs to with equal prominence | Users accidentally create resources in wrong org | Show current org prominently; require explicit switch with confirmation |
| Hiding org context in permission management UI | Admin grants permission in wrong org | Show org name in permission table header; color-code per org |
| Making org a required URL parameter | Breaks existing bookmarks and API scripts | Org is inferred from user's current context; explicit org parameter is optional override |
| Org creation available to any admin | Org sprawl; hundreds of unused orgs | Restrict org creation to global admins; org admins can manage their org but not create new ones |

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Org-scoped permissions:** Often missing regex and group-regex variants — verify all 4 permission types (user, group, regex, group-regex) are org-scoped for ALL 7 resource types
- [ ] **Search result filtering:** Often missing org filter for logged models, scorers, gateway endpoints/secrets/model definitions — verify _filter_search_* functions check org for all filterable resource types, not just experiments and models
- [ ] **Permission cascade on resource delete:** Often missing org context in cascade delete — verify `_delete_can_manage_*_permission` and `_delete_*_permissions_cascade` functions scope to org when cleaning up
- [ ] **Auto-grant MANAGE on create:** Often missing org assignment — verify `_set_can_manage_*_permission` functions include org_id when creating the auto-granted permission
- [ ] **User deletion cleanup:** Already broken for gateway permissions (CONCERNS.md) — verify org-scoped permissions are also cleaned up when a user is removed from an org (not just deleted entirely)
- [ ] **Rename propagation:** Often missing org context — verify `_rename_registered_model_permission` and `_rename_gateway_endpoint_permission` scope their updates to the correct org
- [ ] **GraphQL auth middleware:** Often forgotten in org implementation — verify the GraphQL authorization middleware checks org boundaries
- [ ] **Session contains org context:** Often missing — verify session stores current org and that org switch updates the session
- [ ] **API backward compatibility:** Often breaking — verify all existing API endpoints work without `org_id` parameter (falls back to default org)
- [ ] **Migration rollback:** Often untested — verify Alembic downgrade path works and restores pre-org schema cleanly

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Cross-tenant data leakage via fallback permission | HIGH | Immediate: change DEFAULT_MLFLOW_PERMISSION to NO_PERMISSIONS. Audit logs to identify leaked data. Notify affected tenants. Long-term: add org boundary check. |
| Broken permissions after migration (null org) | MEDIUM | Run a data repair script: `UPDATE experiment_permissions SET org_id = (SELECT id FROM orgs WHERE name = 'default') WHERE org_id IS NULL`. Restart app. |
| OIDC provider doesn't send org claims | LOW | Configure `OIDC_ORG_DETECTION_PLUGIN` or switch to admin-managed org assignment. Users manually assigned to orgs. |
| Permission complexity explosion (unmaintainable code) | HIGH | Stop. Refactor to generic permission resolution. This is a rewrite of utils/permissions.py — budget 1-2 weeks. Defer new org features until refactor lands. |
| Bridge missing org context (silent failures) | MEDIUM | Add org to bridge immediately. Audit all validators for missing org checks. Add assertions that fail-fast if org is None in org-required contexts. |
| Org admin accessing other org resources | HIGH | Revoke org-admin access. Audit API access logs. Add org-scoped admin check. Deploy fix before re-enabling org-admin. |
| Backward compatibility break (existing deployments) | MEDIUM | Publish hotfix: add default org auto-creation on startup if no orgs exist. All config defaults allow org-free operation. Release as patch version. |

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Cross-tenant data leakage via fallback | Phase 1: Core org model + permission resolution | Integration test: User in Org-A cannot access Org-B experiment, even with DEFAULT_MLFLOW_PERMISSION=MANAGE |
| Post-fetch search filtering leaks | Phase 2: Permission resolution update | Integration test: Search results contain zero cross-org resources; pagination math is correct |
| Migration breaks existing permissions | Phase 1: Database migration | Test: upgrade from pre-org schema with existing data; verify all permissions still work |
| OIDC org claim inconsistency | Phase 2: OIDC integration | Test with at least 2 different OIDC providers (e.g., Keycloak + Auth0); test with no org claim configured |
| Permission complexity explosion | **Phase 0: Prerequisite refactoring** | `utils/permissions.py` uses a single generic resolution function before org work starts |
| Plugin boundary violations | Phase 1: Design doc | Design doc explicitly lists what is in-scope vs. out-of-scope for the auth plugin |
| Bridge missing org context | Phase 1: Core implementation | Integration test: Flask validator can read org_id from bridge; fails-fast if missing |
| Group-to-org relationship | Phase 1: Design decision | Design doc documents the chosen model with rationale; migration handles existing groups |
| Admin bypass without org scoping | Phase 1: Core org model | Test: org admin can MANAGE own org resources, CANNOT access other org resources |
| Backward compatibility | All phases | Test scenario: upgrade without any new config; run existing API scripts; verify identical behavior |

## Sources

- Direct codebase analysis: `utils/permissions.py`, `hooks/before_request.py`, `hooks/after_request.py`, `middleware/auth_middleware.py`, `middleware/auth_aware_wsgi_middleware.py`, `bridge/user.py`, `config.py`, `routers/auth.py`, `db/models/`, `validators/gateway.py`
- `.planning/codebase/CONCERNS.md` — identified tech debt, known bugs (gateway fail-open, user deletion cleanup), security considerations
- `.planning/codebase/ARCHITECTURE.md` — bridge layer design, middleware stack, plugin boundary
- `.planning/PROJECT.md` — constraints, out-of-scope items, existing requirements
- OIDC provider documentation: Auth0 Organizations, Keycloak Organizations, Azure AD multi-tenant, Okta Organizations (known behavior from provider docs)
- Multi-tenant authorization patterns: row-level security, org-scoped RBAC, tenant isolation in shared-database architectures (established patterns, HIGH confidence)

---
*Pitfalls research for: Multi-tenant organization support for mlflow-oidc-auth*
*Researched: 2026-03-23*
