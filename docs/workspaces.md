# Workspaces

Workspaces provide multi-tenant resource isolation for MLflow. When enabled, each workspace acts as an independent namespace — users only see experiments, models, webhooks, and trash from the workspace they are currently working in.

> **Requires MLflow >=3.10.** Workspaces are gated by the `MLFLOW_ENABLE_WORKSPACES` feature flag (default: `false`).

## Overview

Without workspaces, all MLflow resources exist in a single global namespace. With workspaces enabled:

- Every experiment, registered model, model version, webhook, and tag belongs to a workspace
- Users must have explicit workspace permission to access any workspace (including "default")
- Switching workspaces in the UI automatically refreshes all views
- The REST API uses the `X-MLFLOW-WORKSPACE` header to specify the active workspace

## Enabling Workspaces

```bash
# Minimum configuration
MLFLOW_ENABLE_WORKSPACES=true

# Optional: control defaults
OIDC_WORKSPACE_DEFAULT_PERMISSION=NO_PERMISSIONS
WORKSPACE_CACHE_MAX_SIZE=1024
WORKSPACE_CACHE_TTL_SECONDS=300
```

See [Configuration](configuration#workspace-settings) for all workspace-related settings.

## Workspace-Scoped Resources

When workspaces are enabled, these resources are automatically scoped to the active workspace:

| Resource | Scoping Mechanism |
|----------|-------------------|
| Experiments | MLflow's workspace-aware tracking store filters by workspace |
| Runs | Scoped through their parent experiment's workspace |
| Registered Models | MLflow's workspace-aware model registry filters by workspace |
| Model Versions | Scoped through their parent model's workspace |
| Webhooks | Treated as workspace-isolated by the model registry store |
| Deleted Experiments (Trash) | Filtered by workspace — restore and hard-delete respect workspace boundaries |
| Registered Model Tags, Aliases | Scoped through their parent model's workspace |

**Not workspace-scoped:**
- Users and groups (global across all workspaces)
- Permission records (global — permissions reference specific resources within workspaces)
- AI Gateway endpoints, secrets, model definitions (not workspace-isolated by MLflow)

## Workspace Permissions

Workspace permissions use the same levels as resource permissions: `READ`, `USE`, `EDIT`, `MANAGE`, `NO_PERMISSIONS`.

| Permission | Access Level |
|------------|-------------|
| `READ` | View the workspace and its resources in search/list results |
| `USE` | Use resources within the workspace |
| `EDIT` | Modify resources within the workspace |
| `MANAGE` | Full control: create experiments/models, manage workspace permissions |
| `NO_PERMISSIONS` | Explicit denial — workspace is hidden from all results |

### No Implicit Access

When workspaces are enabled, there are **no implicit grants** for any workspace. A user without a workspace permission record cannot access that workspace. This applies to all workspaces, including "default".

Admin users bypass all workspace permission checks.

## Workspace Permissions as Resource Fallback

Workspace permissions serve a dual role:

1. **Workspace access control** — gate access to workspace API endpoints and filter workspace lists
2. **Resource-level fallback** — when no explicit resource permission exists (no user, group, regex, or group-regex match), the user's workspace permission is used as the baseline access level

### Resolution Chain with Workspaces

```
1. Resource-level sources (PERMISSION_SOURCE_ORDER):
   user → group → regex → group-regex
2. If no resource-level permission → workspace permission fallback
3. If no workspace permission → NO_PERMISSIONS (denied)
```

When workspaces are enabled, `DEFAULT_MLFLOW_PERMISSION` is **not** used as a resource fallback. The workspace permission takes that role, ensuring workspace boundaries are enforced.

### Example: Workspace Fallback

```
User: alice
Workspace: team-alpha (alice has EDIT workspace permission)
Resource: experiment_789 (in team-alpha workspace)

Resolution:
  - user permission for experiment_789: not found
  - group permission: not found
  - regex match: not found
  - group-regex match: not found
  - Workspace fallback: alice has EDIT on team-alpha
Result: EDIT permission (from workspace fallback)
```

```
User: alice
Workspace: team-beta (alice has no workspace permission)
Resource: experiment_999 (in team-beta workspace)

Resolution:
  - user permission for experiment_999: not found
  - group permission: not found
  - regex match: not found
  - group-regex match: not found
  - Workspace fallback: no permission on team-beta
Result: Access denied (NO_PERMISSIONS)
```

### Implications

- Granting `MANAGE` on a workspace means the user can manage **all resources** in that workspace that lack more specific permissions
- Granting `EDIT` on a workspace allows updating existing experiments and registered models (via workspace fallback) but **does not** allow creating new experiments or models
- To restrict access to specific resources within a workspace, assign explicit resource-level permissions (they always take priority over the workspace fallback)
- The workspace fallback only applies when `MLFLOW_ENABLE_WORKSPACES=true`

### Creation vs Update Behavior

With workspaces enabled, creation is intentionally stricter than update:

- `CreateExperiment` requires workspace `MANAGE`
- `CreateRegisteredModel` requires workspace `MANAGE`
- Updating existing experiments/models follows normal permission resolution, so workspace `EDIT` fallback is sufficient for update operations when no resource-level override exists

#### Hardening creation for clients that send no workspace context

A client that omits the `X-MLFLOW-WORKSPACE` header still creates resources — MLflow resolves such a
request to the `default` workspace. By default this path is not workspace-gated, which preserves
backward compatibility. Two opt-in settings tighten it:

- `OIDC_WORKSPACE_REQUIRE_CREATION_CONTEXT=true` rejects workspace-gated create requests that carry no
  workspace context at all, forcing clients to be explicit about their target workspace.
- `OIDC_WORKSPACE_DENY_DEFAULT_CREATION=true` rejects non-admin creates that land in the `default`
  workspace. Because a request with no workspace context lands there too, this also covers clients
  that omit the header — it cannot be bypassed by dropping the header.

Admins bypass both guards. Enabling both gives the strictest posture: every non-admin create must name
a non-default workspace on which the user holds `MANAGE`.

This means the following setup allows users to edit existing resources but not create new ones:

```bash
MLFLOW_ENABLE_WORKSPACES=true
OIDC_WORKSPACE_DEFAULT_PERMISSION=EDIT
```

## `NO_PERMISSIONS` vs No Record

- **`NO_PERMISSIONS` assigned**: The user is explicitly denied. `can_read` is `false`. The workspace is hidden from all results.
- **No permission record**: No explicit permission exists. The workspace is also inaccessible (there is no implicit default grant).

In practice, both result in denial. The distinction matters for auditing — `NO_PERMISSIONS` is an intentional block, while no record means the user was never granted access.

## Enforcement Points

| Context | Enforcement |
|---------|-------------|
| **Workspace API** | `GetWorkspace`, `UpdateWorkspace`, `DeleteWorkspace`, `CreateWorkspace`, `ListWorkspaces` are gated by workspace permission checks |
| **Resource creation** | `CreateExperiment` and `CreateRegisteredModel` require `MANAGE` on the target workspace |
| **Search/list filtering** | `SearchExperiments`, `SearchRegisteredModels`, `SearchLoggedModels`, `ListWorkspaces` are filtered to readable workspaces |
| **Permission management** | Workspace permission CRUD endpoints require `MANAGE` on the workspace |
| **Trash** | Deleted experiments and runs are filtered by workspace. Restore and hard-delete are workspace-scoped |
| **Webhooks** | Webhook CRUD operations are scoped to the active workspace |

## Workspace Detection During Login

When a user logs in via OIDC, the plugin can automatically detect and provision workspace access:

1. **Plugin detection**: If `OIDC_WORKSPACE_DETECTION_PLUGIN` is configured, the plugin extracts workspace assignments from the access token
2. **Claim-based detection**: Falls back to reading the `OIDC_WORKSPACE_CLAIM_NAME` claim from the OIDC token (default claim: `workspace`)
3. **Auto-provisioning**: Detected workspaces are created if they don't exist, and the user is assigned `OIDC_WORKSPACE_DEFAULT_PERMISSION` (default: `NO_PERMISSIONS`)

### Configuration

```bash
# Token claim containing workspace name(s)
OIDC_WORKSPACE_CLAIM_NAME=workspace

# Custom plugin for workspace detection
OIDC_WORKSPACE_DETECTION_PLUGIN=mypackage.workspace_detector

# Permission level for auto-detected workspaces
OIDC_WORKSPACE_DEFAULT_PERMISSION=READ
```

If you set `OIDC_WORKSPACE_DEFAULT_PERMISSION=EDIT`, newly auto-assigned users can modify existing resources in that workspace but cannot create new experiments or registered models until granted workspace `MANAGE`.

## Workspace Permission Cache

To avoid repeated database lookups, workspace permissions are cached in memory:

```bash
# Maximum cache entries (default: 1024)
WORKSPACE_CACHE_MAX_SIZE=1024

# Cache TTL in seconds (default: 300 = 5 minutes)
WORKSPACE_CACHE_TTL_SECONDS=300
```

The cache is automatically flushed when:
- A workspace is created or deleted
- Workspace permissions are created, updated, or deleted via the API

In multi-replica deployments, each replica has its own cache. Permission changes may take up to `WORKSPACE_CACHE_TTL_SECONDS` to propagate to other replicas.

## Workspace Regex Permissions

Workspace permissions also support regex patterns, allowing pattern-based workspace access:

```
# Grant READ to all workspaces matching "team-*"
Pattern: ^team-.*
Permission: READ
```

Both user-level and group-level workspace regex permissions are supported through the `/api/3.0/mlflow/permissions/workspaces/regex/` endpoints. These are admin-only operations.

## Group rules

A group rule attaches groups to workspaces by the group's **name**, so onboarding a tenant is
"create the group in the identity provider" rather than "create the group, then attach it to its
workspace by hand". A rule grants a workspace group permission — the existing tenant boundary — and
never touches individual experiments or models.

```
Name:        tenants
Pattern:     ^team-(?P<ws>[a-z0-9-]+)-ds$
Permission:  EDIT
Mode:        enforce
```

With this rule, the group `team-acme-ds` gets `EDIT` on the workspace `acme`, and
`team-globex-ds` gets `EDIT` on `globex`.

### How a rule matches

- `pattern` is a Python regular expression matched with `re.fullmatch` — the **whole** group name
  must match, never a part of it. It must contain the named group `(?P<ws>...)`, whose match is the
  workspace name, and be at most 256 characters.
- It is matched against the **local** group name. A group from a provider other than `default`
  carries the provider's prefix — a partner provider's `team-acme-ds` is stored as
  `partner:team-acme-ds` — so a rule written for your own groups never matches a partner's. To
  cover a partner, write a rule for its namespace: `^partner:team-(?P<ws>[a-z0-9-]+)-ds$`.
- A group created by a provider other than `default` is only ever matched under its prefixed name.
- The workspace must already exist. A group whose workspace does not exist is skipped and reported;
  rules never create workspaces.
- The shared `default` workspace is never granted by a rule, whatever the pattern matches. Grant it
  by hand.

Whoever can create a group whose name matches a rule gets the rule's permission — in your identity
provider, that may be more people than you think. Keep patterns narrow (anchor the workspace part to
the names you expect, e.g. `(?P<ws>acme|globex)`), and prefer a low permission. Patterns run on
every login that creates a group; avoid nested quantifiers such as `(a+)+`, which can take very long
on a long group name.

### What a rule may grant

- `READ`, `USE` or `EDIT` by default. The ceiling is `WORKSPACE_RULES_MAX_PERMISSION`; `MANAGE`
  is possible only when an operator raises it to `MANAGE`, and the server warns at startup when it
  is. The ceiling is checked when a rule is saved **and** when it is applied. After lowering it,
  restart the server: at startup, every grant held by a rule above the new ceiling is removed
  (audited as `permission.deprovisioned` by `system:workspace-rules-ceiling`); the rule stays and
  reports `skip` until you lower its permission.
- `NO_PERMISSIONS` is not a rule permission, and a rule never makes anyone an administrator.

### Who owns a grant

Every grant a rule creates records the rule (`rule_id`); a grant made by hand has none. A rule only
ever creates, changes or removes its **own** grants:

- If a manual grant already exists for the same group and workspace, the rule leaves it alone and
  reports `skip: manual grant` — whether the manual grant is higher or lower than the rule's.
- Editing a rule's grant through the workspace-permission API makes it a manual grant: no rule
  changes or removes it again. `GET /api/3.0/mlflow/permissions/workspaces/{workspace}/groups`
  shows each grant's `rule_id` (`null` for manual).
- Deleting a rule's grant by hand does not stop the rule: the next backfill grants it again. To stop
  a rule granting one group, narrow the pattern, or give the group a manual grant.

When several rules match the same group and workspace, the rule with the **lowest id** wins and the
others report `shadowed`. Only enabled `enforce` rules compete; a `report` rule never shadows one.
No rule ever writes another rule's grant: when a lower-id rule starts enforcing while a higher-id one
holds a group it wins, the higher-id rule releases its grant and the winner grants its own. When
the winner is deleted, disabled or switched to `report`, the rule it shadowed takes the group over
the same way.

### When rules run

| Event | What happens |
|---|---|
| A group arrives — SCIM `POST /Groups`, admin `POST .../permissions/groups`, or a login that creates groups | Every enabled `enforce` rule is applied to the groups that arrived, and only those. |
| A rule is created, updated or enabled | The rule is backfilled over every existing group: it grants what it matches and removes the grants it holds that it no longer matches. |
| A rule is deleted, disabled or switched to `report` | Only that rule's grants are removed; the other enforcing rules are then applied to the groups that lost one. |
| A rule is only renamed | Nothing: no grant changes. |
| A rule is saved again with a grant field, even unchanged | Backfilled, as on update — the way to retry after a failed backfill. |

If MLflow's workspace store cannot be reached, a rule writes nothing — it never reads an outage as
"the workspace does not exist", which would remove its grants. A rule saved during an outage is
saved; its response carries an `error`, and saving it again with any of its pattern, permission,
mode or enabled — even unchanged — retries. Groups that arrive any other
way are picked up by the next backfill. A rule failing on arrival is logged and audited (`workspace_rule.failed`) and never fails
the login or the SCIM request that brought the group.

### Report mode

A new rule defaults to `mode: report`: it writes nothing, and its create, update and preview
responses list what enforcing it would grant, update, keep, skip or remove. Switch it to `enforce`
once the list is what you expect. `POST /api/3.0/mlflow/workspace-rules/preview` shows the same for
a rule that is not saved yet, or — with `rule_id` — for unsaved changes to an existing rule.

### Audit

| Event | When |
|---|---|
| `workspace_rule.create` / `.update` / `.delete` | An administrator changes a rule |
| `permission.provisioned` | A rule created or changed a grant; `detail` holds `rule_id`, `workspace`, `group`, `permission` (and `previous` for a change) |
| `permission.deprovisioned` | A rule removed one of its grants |
| `workspace_rule.skipped` | An enforcing rule left a group alone; `detail.reason` says why (`manual grant`, `workspace does not exist`, `held by rule N`, a shadowing rule, the ceiling, the `default` workspace) |
| `workspace_rule.failed` | A rule could not run for groups that arrived, or a saved rule's backfill failed (`detail.operation: backfill`) |

The actor is the administrator for rule changes and backfills, and the source that brought the
group for arrivals (`scim`, `oidc:<provider>`, `saml:<provider>`, or the admin's username).

Everything here is inert, and the API answers `404`, unless `MLFLOW_ENABLE_WORKSPACES=true`. Rule
management is admin-only.

## API Reference

### Workspace CRUD (MLflow Native)

Workspace lifecycle is handled by MLflow's native workspace API. The auth plugin enforces permission checks via `before_request` / `after_request` hooks.

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | `/api/3.0/mlflow/workspaces` | Admin | Create workspace |
| GET | `/api/3.0/mlflow/workspaces` | Authenticated | List workspaces (filtered by permission) |
| GET | `/api/3.0/mlflow/workspaces/{workspace_name}` | Workspace READ | Get workspace details |
| PATCH | `/api/3.0/mlflow/workspaces/{workspace_name}` | Workspace MANAGE | Update workspace |
| DELETE | `/api/3.0/mlflow/workspaces/{workspace_name}` | Workspace MANAGE | Delete workspace |

### Workspace Permissions

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/api/3.0/mlflow/permissions/workspaces/{workspace}/users` | Workspace READ | List user permissions |
| POST | `/api/3.0/mlflow/permissions/workspaces/{workspace}/users` | Workspace MANAGE | Create user permission |
| PATCH | `/api/3.0/mlflow/permissions/workspaces/{workspace}/users/{username}` | Workspace MANAGE | Update user permission |
| DELETE | `/api/3.0/mlflow/permissions/workspaces/{workspace}/users/{username}` | Workspace MANAGE | Delete user permission |
| GET | `/api/3.0/mlflow/permissions/workspaces/{workspace}/groups` | Workspace READ | List group permissions |
| POST | `/api/3.0/mlflow/permissions/workspaces/{workspace}/groups` | Workspace MANAGE | Create group permission |
| PATCH | `/api/3.0/mlflow/permissions/workspaces/{workspace}/groups/{group_name}` | Workspace MANAGE | Update group permission |
| DELETE | `/api/3.0/mlflow/permissions/workspaces/{workspace}/groups/{group_name}` | Workspace MANAGE | Delete group permission |

### Workspace Regex Permissions (Admin Only)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/3.0/mlflow/permissions/workspaces/regex/user` | Create user regex permission |
| GET | `/api/3.0/mlflow/permissions/workspaces/regex/user` | List user regex permissions |
| PATCH | `/api/3.0/mlflow/permissions/workspaces/regex/user/{id}` | Update user regex permission |
| DELETE | `/api/3.0/mlflow/permissions/workspaces/regex/user/{id}` | Delete user regex permission |
| POST | `/api/3.0/mlflow/permissions/workspaces/regex/group` | Create group regex permission |
| GET | `/api/3.0/mlflow/permissions/workspaces/regex/group` | List group regex permissions |
| PATCH | `/api/3.0/mlflow/permissions/workspaces/regex/group/{id}` | Update group regex permission |
| DELETE | `/api/3.0/mlflow/permissions/workspaces/regex/group/{id}` | Delete group regex permission |

### Workspace Group Rules (Admin Only)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/3.0/mlflow/workspace-rules` | List rules and the permission ceiling |
| POST | `/api/3.0/mlflow/workspace-rules` | Create a rule and backfill it |
| POST | `/api/3.0/mlflow/workspace-rules/preview` | Preview an unsaved rule |
| GET | `/api/3.0/mlflow/workspace-rules/{id}` | Get a rule |
| PATCH | `/api/3.0/mlflow/workspace-rules/{id}` | Update a rule and reconcile its grants |
| DELETE | `/api/3.0/mlflow/workspace-rules/{id}` | Delete a rule and its grants |
| GET | `/api/3.0/mlflow/workspace-rules/{id}/preview` | Preview a rule against current groups |

See the full [API Reference](api-reference) for request/response schemas.

## Limitations and non-goals

These are deliberate exclusions, not gaps. They are listed so you can plan around them rather
than discover them.

| Not supported | Why |
|---|---|
| Workspace hierarchy / nesting | MLflow's workspace model is flat. Nesting would make permission resolution exponentially more complex for a case MLflow itself does not represent. |
| Moving a resource between workspaces | Not supported by MLflow — an experiment or model must be recreated in the target workspace. |
| Per-workspace redefinition of RBAC levels | `READ` / `USE` / `EDIT` / `MANAGE` mean the same thing everywhere. Per-workspace semantics would make a permission audit unreadable. |
| Per-workspace artifact store management in the UI | An MLflow core responsibility. `default_artifact_root` is set at creation time only. |
| Workspace templates | Set up each workspace explicitly, or script it against the API. |
| Workspace usage analytics | Not an authorization concern — use MLflow's own UI. |
| Cross-instance workspace federation | This plugin secures a single MLflow instance. |

Workspace CRUD always proxies through the MLflow API rather than writing to MLflow's store
directly, so MLflow's own validation and constraints continue to apply.
