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
| Prompts | Registered models, scoped the same way |
| AI Gateway endpoints, secrets, model definitions | MLflow's tracking store keeps them per workspace |

**Not workspace-scoped:**
- Users and groups (global across all workspaces)

### Pattern (regex) grants

A pattern grant on experiments, models, prompts, scorers or AI Gateway resources applies in the
workspace it was made in: one created with a workspace named (`X-MLFLOW-WORKSPACE` — in the admin
UI, the workspace selected in the picker) matches only that workspace's resources. One created with
no workspace named (**All Workspaces**) applies in every workspace. Patterns are created by
administrators only, and each lists the workspace it applies in (`*` for every workspace).

- The same pattern may be recorded once per workspace, with a different permission in each.
- Patterns from before this release apply in every workspace, as they did.
- Deleting a workspace removes its patterns; patterns for every workspace stay.
- With workspaces disabled, patterns for every workspace apply; a pattern recorded for one
  workspace counts only if workspaces are enabled again.
- **Downgrading** keeps only patterns for every workspace — a pattern recorded for one workspace
  would otherwise apply in all of them — and logs how many were removed.

### Grants on models, prompts and gateway resources

MLflow keeps registered models, prompts and AI Gateway endpoints, secrets and model definitions
unique per **workspace and name**: two workspaces can each have a model called `churn`. A grant on
one of them — to a user or a group — therefore belongs to one workspace's resource:

- A grant is recorded in the workspace the request names (`X-MLFLOW-WORKSPACE`), or in the
  `default` workspace when it names none. The admin UI sends the workspace chosen in the workspace
  picker; with **All Workspaces** selected it sends none, so grants are made and listed in `default`.
- A grant applies only to requests in that workspace. A grant on `churn` in `team-a` gives nothing
  on `team-b`'s `churn`, and creating a same-named resource in another workspace grants its creator
  nothing on this one.
- Deleting or renaming a resource updates only the grants of that workspace's resource.
- The permission API lists and changes the grants of the request's workspace.
- Experiment and scorer grants are keyed by experiment id, which MLflow keeps unique across
  workspaces, so they need no workspace of their own.

With workspaces disabled every resource lives in `default`, new grants record it, and only the
`default` workspace's grants (and grants from before this release) count — for a deployment that
never enabled workspaces, that is every grant, so behaviour is unchanged. A deployment that turns
workspaces off again keeps its other workspaces' grants, but they count only if workspaces are
enabled again.

#### Upgrading: existing grants

Grants made before this release carry no workspace. They are assigned one automatically on every
start, before the server takes requests. When several workers start at once, one of them assigns
them and the others change nothing:

| Workspaces | What happens to an existing grant |
|---|---|
| Disabled | It is assigned `default`. |
| Enabled | It is kept in each workspace that has a resource of that name **and** where the grantee already has at least `READ`. The `default` workspace is the exception: it holds the resources from before workspaces were enabled, so a grant on a name found there is kept there when the grantee reaches no workspace holding that name. A grantee who reaches another such workspace keeps the grant only there — a tenant who created a same-named resource in their own workspace does not come away owning `default`'s. |
| Enabled, no such workspace, or the resource no longer exists | It is marked **unresolved**: it matches nothing — with workspaces disabled too — and is never placed later, so a resource created afterwards does not pick it up. It is listed in a startup warning and a `permission.workspace_unresolved` audit event. Re-grant it in the right workspace. |

An old grant reached every workspace's resource of its name — including ones another tenant created
later — so a workspace's resource keeps it only where the grantee could already reach that
workspace. Where a grant for the same workspace, resource and principal already exists, the
existing one is kept.

Deleting a workspace now also removes the grants on its models, prompts and gateway resources, so a
workspace created later under the same name starts without them. When MLflow moves a deleted
workspace's resources to `default` instead of deleting them, those resources arrive without grants
and only administrators can manage them until they are granted again.

A grant on a single model, prompt or gateway resource applies to its holder whether or not they
have a permission on the workspace itself — that is how one resource is shared with someone outside
the workspace. Removing someone's workspace permission does not remove such grants; revoke them on
the resource.

**Upgrade all replicas together.** While a replica on an older release writes grants, it writes them
without a workspace; a request touching such a grant can fail until the next restart assigns it.

**Downgrading** keeps only the `default` workspace's grants — a grant recorded for another workspace
would otherwise apply to every workspace's resource of that name — and logs how many were removed.

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

### MCP server registry

MLflow keeps an MCP server registry per workspace. Reading it requires at least `READ` on the
workspace the request names — the default workspace when it names none — like any other
workspace-scoped resource. Changing it is admin-only.

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

### Examples

Each example shows the rule, then what it does to groups that exist or arrive. The workspaces
`acme`, `globex` and `initech` exist; `umbrella` does not.

#### One rule for every tenant

Every tenant's data-science group follows one naming convention:

```
Name:        tenant data scientists
Pattern:     ^team-(?P<ws>[a-z0-9-]+)-ds$
Permission:  EDIT
Mode:        enforce
```

| Group | Result |
|---|---|
| `team-acme-ds` | `EDIT` on `acme` |
| `team-globex-ds` | `EDIT` on `globex` |
| `team-umbrella-ds` | skip: workspace does not exist — granted automatically once the workspace is created and the rule is saved again |
| `team-default-ds` | skip: the default workspace is never granted by a rule |
| `team-acme-ds-old` | no match — the whole name must match |
| `partner:team-acme-ds` | no match — a partner provider's group carries its prefix |

Onboarding a new tenant is now: create the workspace, create `team-<tenant>-ds` in the identity
provider. The group gets `EDIT` the moment SCIM, an admin or a member's first login brings it in.

#### Different access for different groups of a tenant

Two rules, one per suffix. They never compete, because no group matches both:

```
Name:        tenant engineers      Pattern: ^team-(?P<ws>[a-z0-9-]+)-eng$      Permission: EDIT
Name:        tenant viewers        Pattern: ^team-(?P<ws>[a-z0-9-]+)-viewers$  Permission: READ
```

`team-acme-eng` gets `EDIT` on `acme`; `team-acme-viewers` gets `READ` on `acme`. A member of both
groups gets the higher of the two, as with any group grant.

#### Only the tenants you name

A pattern that captures any name trusts whoever can create groups in the directory. To admit only
known tenants, list them in the workspace group:

```
Pattern:     ^team-(?P<ws>acme|globex)-ds$
```

`team-acme-ds` and `team-globex-ds` match; `team-initech-ds` does not, even though `initech` exists.
Add a tenant by editing the pattern — saving it backfills the new tenant's group.

#### A partner identity provider

Groups from a provider other than `default` are stored as `<provider-id>:<name>`. A rule for them
names that prefix, so it can never match your own groups, and yours never match theirs:

```
Name:        partner analysts
Pattern:     ^partner:analysts-(?P<ws>[a-z0-9-]+)$
Permission:  READ
```

`partner:analysts-acme` gets `READ` on `acme`. A group called `analysts-acme` from your own provider
does not match this rule.

#### Overlapping rules

```
Rule 1   Pattern: ^team-(?P<ws>[a-z0-9-]+)-ds$            Permission: READ
Rule 2   Pattern: ^team-(?P<ws>[a-z0-9-]+)-(ds|ml)$       Permission: EDIT
```

| Group | Result |
|---|---|
| `team-acme-ds` | `READ` from rule 1; rule 2 reports `shadowed` (the lowest id wins) |
| `team-acme-ml` | `EDIT` from rule 2 — rule 1 does not match it |

Delete or disable rule 1 and rule 2 takes `team-acme-ds` over with `EDIT`. To give one group more
than a broad rule does, a narrower rule is not enough when the broad one is older — give that group
a manual grant instead, which no rule ever overrides.

#### A single group

The rule builder in the admin UI writes this for one group and its workspace:

```
Pattern:     ^team-(?P<ws>acme)-ds$
```

It matches `team-acme-ds` and nothing else. The workspace part is still a named group, because a rule
always takes the workspace from the group's name.

#### What a rule cannot do

| You want | Why a rule cannot | Instead |
|---|---|---|
| `data-scientists` → `acme` | The group name does not contain the workspace name, so there is nothing for `(?P<ws>...)` to capture | Grant the group on the workspace's page |
| Anyone → the `default` workspace | Rules never grant it | Grant it by hand |
| A workspace created on demand | Rules never create workspaces | Create the workspace; save the rule again to backfill |
| `MANAGE` | Above the default ceiling | Raise `WORKSPACE_RULES_MAX_PERMISSION` — and read the startup warning |

#### Rolling a rule out through the API

Create it in `report` mode, read what it would do, then enforce it:

```bash
MLFLOW=https://mlflow.example.com
AUTH="-u admin@example.com:$ADMIN_TOKEN"

# 1. Create in report mode (the default): nothing is written, the response lists the plan.
curl $AUTH -X POST "$MLFLOW/api/3.0/mlflow/workspace-rules" \
  -H "Content-Type: application/json" \
  -d '{"name": "tenant data scientists", "pattern": "^team-(?P<ws>[a-z0-9-]+)-ds$", "permission": "EDIT"}'

# 2. Preview it again later, against the groups that exist by then.
curl $AUTH "$MLFLOW/api/3.0/mlflow/workspace-rules/1/preview"

# 3. Enforce it: the response lists every grant written.
curl $AUTH -X PATCH "$MLFLOW/api/3.0/mlflow/workspace-rules/1" \
  -H "Content-Type: application/json" -d '{"mode": "enforce"}'
```

A plan line looks like
`{"action": "grant", "group": "team-acme-ds", "workspace": "acme", "permission": "EDIT", "applied": true, ...}`;
see the [API reference](api-reference#workspace-group-rules-admin-only) for every field.

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
