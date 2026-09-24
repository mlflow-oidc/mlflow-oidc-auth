# Permission System

The plugin enforces role-based access control (RBAC) on all MLflow resources. Every API request is checked against the permission system before reaching MLflow.

## Permission Levels

Five permission levels form a hierarchy:

| Level | Priority | can_read | can_use | can_update | can_delete | can_manage |
|-------|----------|----------|---------|------------|------------|------------|
| `READ` | 1 | Yes | - | - | - | - |
| `USE` | 2 | Yes | Yes | - | - | - |
| `EDIT` | 3 | Yes | Yes | Yes | - | - |
| `MANAGE` | 4 | Yes | Yes | Yes | Yes | Yes |
| `NO_PERMISSIONS` | 100 | - | - | - | - | - |

- **Higher priority wins** when multiple permissions exist (e.g., group A grants READ, group B grants MANAGE — the user gets MANAGE)
- **`NO_PERMISSIONS`** is an explicit denial, not the absence of a permission record. It actively blocks access regardless of other sources
- **Admin users** bypass all permission checks entirely

## Protected Resources

The permission system covers these MLflow resource types:

| Resource | Permission Scope | Notes |
|----------|-----------------|-------|
| Experiments | Per experiment ID | Includes runs within the experiment |
| Registered Models | Per model name | Includes model versions |
| Prompts | Per prompt name | Uses the model permission infrastructure |
| Scorers | Per experiment + scorer name | Compound key |
| Prompt Optimization Jobs | Per job → experiment ID | Job-level operations resolve to the parent experiment's permissions |
| Gateway Endpoints | Per endpoint name | AI Gateway routes |
| Gateway Secrets | Per secret name | AI Gateway secrets |
| Gateway Model Definitions | Per model definition name | AI Gateway model configs |
| Workspaces | Per workspace name | Only when `MLFLOW_ENABLE_WORKSPACES=true`. See [Workspaces](workspaces) |

## Permission Sources

Permissions can come from four sources. Each source is checked in the order configured by `PERMISSION_SOURCE_ORDER`.

### Source Types

| Source | Key | Description |
|--------|-----|-------------|
| User permission | `user` | Direct permission assigned to a specific user for a specific resource |
| Group permission | `group` | Permission assigned to a group — inherited by all members. When a user belongs to multiple groups, the highest permission wins |
| Regex permission | `regex` | User-specific regex pattern that matches resource names. Patterns are evaluated by priority (lower number = checked first) |
| Group regex permission | `group-regex` | Group-level regex pattern — inherited by all members. Evaluated by priority like user regex |

### Resolution Order

```
PERMISSION_SOURCE_ORDER=user,group,regex,group-regex
```

The system checks each source in order and uses the **first permission found**:

1. Check `user` — is there a direct permission for this user + resource?
2. Check `group` — does any of the user's groups have a permission for this resource?
3. Check `regex` — does any of the user's regex patterns match this resource name?
4. Check `group-regex` — does any group regex pattern match?
5. **Fallback**:
   - If workspaces enabled → use workspace permission (see [Workspace Fallback](workspaces#workspace-permissions-as-resource-fallback))
   - If workspaces disabled → use `DEFAULT_MLFLOW_PERMISSION`

Within a single source type (e.g., `group`), if multiple entries match, the **highest permission level wins** (MANAGE > EDIT > USE > READ).

### Which request source is authorized

A resource id can reach MLflow in the URL path, the query string, or the request body.
The plugin reads the id from the same place MLflow will: on a protobuf API route that is
the path parameter if there is one, otherwise the query string for a `GET` that has one
and the JSON body for every other request (the query string is ignored on `POST`,
`PATCH` and `DELETE`). `/ajax-api/2.0/mlflow/upload-artifact` uses the query string only,
and `gateway-proxy` uses the query string on `GET` and the body otherwise.

Every other value the request carries for that field — in any source, under either the
`snake_case` or the `camelCase` spelling — is authorized as well. If a request names two
different resources for one field, the caller needs the permission on both, or the
request is denied with `403`. A request that is missing the id where MLflow reads it is
refused (`400` or `403`); the id is never taken from a source MLflow ignores instead.
Ordinary clients send each id once, or the same id in two places, so they are not
affected.

## Regex Permissions

Regex permissions use Python regular expression syntax to match resource names by pattern rather than by individual resource ID.

### How They Work

1. Patterns are ordered by **priority** (lower number = checked first)
2. The **first matching pattern** determines the permission
3. Both user-level and group-level regex permissions are supported

### Pattern Examples

| Pattern | Matches |
|---------|---------|
| `.*` | Any resource name |
| `^prod-.*` | Names starting with "prod-" |
| `.*-test$` | Names ending with "-test" |
| `^(dev\|staging)-.*` | Names starting with "dev-" or "staging-" |
| `^team-alpha/.*` | Names under the "team-alpha/" namespace |

### Regex Resolution Example

```
User regex permissions for experiments:
  Priority 1: "^prod-.*"      → NO_PERMISSIONS
  Priority 2: "^dev-.*"       → MANAGE
  Priority 3: ".*"            → READ

For experiment "dev-ml-model":
  1. Check "^prod-.*"   → no match
  2. Check "^dev-.*"    → match → MANAGE
  Result: MANAGE permission
```

### Regex Safety (ReDoS Protection)

Regex patterns are validated on creation/update to prevent Regular Expression Denial of Service (ReDoS) attacks:

- **Maximum pattern length**: 1024 characters. Patterns exceeding this limit are rejected
- **Nested quantifier detection**: Patterns containing nested quantifiers (e.g., `(a+)+`, `(a*)*b`, `(a{2,}){3,}`) are rejected because they can cause catastrophic backtracking
- **Validation errors**: When a pattern is rejected, the server returns an HTTP 400 response with a descriptive error message (e.g., "Pattern exceeds maximum length of 1024 characters" or "Potentially unsafe regex pattern detected: nested quantifiers")

These limits are hardcoded and cannot be configured via environment variables.

## Auto-Grant on Resource Creation

When a user creates a resource, the plugin automatically grants them `MANAGE` permission on it. This applies to:

- `CreateExperiment` → MANAGE on the new experiment
- `CreateRegisteredModel` → MANAGE on the new model
- `RegisterScorer` → MANAGE on the new scorer
- `CreateGatewayEndpoint` → MANAGE on the new endpoint
- `CreateGatewaySecret` → MANAGE on the new secret
- `CreateGatewayModelDefinition` → MANAGE on the new model definition
- `CreateWorkspace` → MANAGE workspace permission (when workspaces enabled)

## Search Result Filtering

For non-admin users, search and list results are filtered to only include resources the user can read:

- `SearchExperiments` — removes experiments the user cannot read
- `SearchRegisteredModels` — removes models the user cannot read
- `SearchModelVersions` — removes model versions whose parent model is unreadable
- `SearchLoggedModels` — removes logged models whose parent experiment is unreadable
- `ListGatewayEndpoints` — removes unreadable gateway endpoints
- `ListGatewaySecretInfos` — removes unreadable gateway secrets
- `ListGatewayModelDefinitions` — removes unreadable model definitions
- `ListWorkspaces` — removes workspaces the user has no READ permission for

The filtering preserves MLflow's pagination contract — the system continues fetching additional pages until the requested `max_results` is satisfied or no more results exist.

## HEAD Requests and Route Coverage

A `HEAD` request is authorized exactly like the `GET` it mirrors. werkzeug serves `HEAD` through the `GET` view and keeps the `Content-Length` header, so it gets the same validator and the same search filtering as its `GET` twin. A caller who cannot read a resource cannot use `HEAD` to learn whether it exists or how large it is. Coverage of MLflow's API is checked by a test, `mlflow_oidc_auth/tests/hooks/test_validator_coverage_sweep.py`. It walks every route and method in MLflow's Flask routing table, with `HEAD` folded onto `GET`, and every protobuf message MLflow registers. The test fails on any route, or any mutating message (`Log*`, `Set*`, `Delete*`, `Create*`, …), that does not fall into one of these groups: mapped to a validator, filtered after the request, admin-only, on the documented list of open routes, or on a list of routes still awaiting a validator. That last list can only shrink, and follow-up changes are emptying it. A route MLflow adds later therefore fails the test until it is classified. MLflow's own registry webhook API is admin-only. Its deliveries are not scoped to a tenant, so it is gated the same way as the plugin's own webhook API.

## Permission Cascade on Delete/Rename

When resources are deleted or renamed, associated permissions are automatically updated:

| Event | Action |
|-------|--------|
| Delete registered model | All user and group permissions for that model are deleted |
| Delete scorer | All scorer permissions are deleted |
| Delete gateway endpoint/secret/model definition | All associated permissions are deleted |
| Rename registered model | All permission records are updated to the new name |
| Rename gateway endpoint | All endpoint permission records are updated to the new name |
| Delete workspace | All workspace permissions are deleted, cache is flushed |

## Gateway Permissions

AI Gateway resources (endpoints, secrets, model definitions) use the same permission system as experiments and models. Permission sources (user, group, regex, group-regex) are evaluated in the same order.

Gateway permissions are managed through:
- **Admin UI**: The gateway section (when `OIDC_GEN_AI_GATEWAY_ENABLED=true`)
- **REST API**: `/api/2.0/mlflow/permissions/gateways/` endpoints
- **Before-request hooks**: Enforce permissions on all gateway operations

## GraphQL Authorization

The plugin enforces permissions on MLflow's GraphQL API (`/graphql`) through a custom middleware:

- **Protected operations**: `mlflowGetExperiment`, `mlflowGetRun`, `mlflowListArtifacts`, `mlflowSearchRuns`, `mlflowSearchDatasets`, `mlflowSearchModelVersions`, and related fields
- **Behavior**: Returns `null` for unauthorized fields (does not raise errors)
- **Admin users**: Bypass all GraphQL authorization checks

## Workspace Permissions

For workspace-specific permission behavior, see [Workspaces](workspaces).

Key points:
- Workspace permissions serve a dual role: workspace access control **and** resource-level fallback
- When workspaces are enabled, `DEFAULT_MLFLOW_PERMISSION` is not used as a resource fallback — workspace permissions take that role
- With `MLFLOW_ENABLE_WORKSPACES=true` and `OIDC_WORKSPACE_DEFAULT_PERMISSION=EDIT`, users can update existing experiments/models through workspace fallback but cannot create new experiments/models (creation requires workspace `MANAGE`)
- All workspace-isolated resources (experiments, models, webhooks, trash) are automatically scoped to the active workspace

## De-provisioning

Deactivating a user — through SCIM (`PATCH active:false`) or the admin API
(`PATCH /api/2.0/mlflow/users/{username}/active`) — does not touch their permission grants.
`users.active` is set to false, every live session and the user's access token are revoked
immediately, and the account row and **every permission grant are kept**. Reactivation restores
access with no re-granting: the user signs in again, or is issued a new access token, and their
prior grants apply exactly as before.

On deactivation and on hard delete, the plugin looks for resources where the departing user was
the **last holder of `MANAGE`** across experiments, registered models, prompts, scorers, gateway
endpoints, model definitions, secrets, and workspaces, and emits a `resource.orphaned` audit event
per resource.

The departing user's resources are the ones they hold `MANAGE` on **directly** or **through a
group**; `detail.via` on the event says which (`"direct"` or `"group:<name>"`). A resource they could
manage only through a regex grant is not enumerated: a pattern matches resources in MLflow, including
ones that do not exist yet.

Another user still holds the resource, so it is **not** orphaned, when that user is active, is not
the departing user, and their permission on it resolves to `MANAGE`. That permission is resolved the
way it is at request time, by replaying `PERMISSION_SOURCE_ORDER`: the first source that has an answer
decides. The sources are:

| Source | Answer |
|---|---|
| `user` | the user's direct grant on the resource |
| `group` | the most permissive grant any of the user's groups holds on it |
| `regex` | the user's own patterns |
| `group-regex` | the patterns of the user's groups |

Some consequences under the default order (`user,group,regex,group-regex`):

- A colleague with a direct `READ` grant is **not** a holder, even if one of their groups holds
  `MANAGE`, or one of their patterns says `MANAGE`.
- A colleague with a direct `MANAGE` grant is a holder, even if one of their groups only reads.
- A group in which the departing user was the **last active member** holds nothing. Resources the
  departing user managed only through that group are reported as `via: "group:<name>"`.

Patterns resolve as they do at request time. They are tried in priority order and the first match
wins; for workspaces, the most permissive of the best-priority matches wins. Each pattern is matched
against the same value the resolver uses:

- experiments: the experiment **name**
- registered models and prompts: the name, using model patterns for models and prompt patterns for
  prompts
- scorers: the scorer name
- gateway resources and workspaces: their name

Experiment names and the model-or-prompt distinction come from MLflow. With workspaces enabled, each
lookup is tried in every workspace. A name that is a model in one workspace and a prompt in another
must be held as both. At most 1000 store calls are made per resource type. When the answer depends on
a lookup that fails, the resource is reported with `via: "unresolved"` and a warning is logged, and it
is **never** handed over. Administrators are not counted, because an administrator can always recover
a resource.

When `ORPHAN_FALLBACK_PRINCIPAL` names an active user, a hard delete also grants that user `MANAGE`
on each orphaned resource, except unresolved ones. Deactivation never transfers, since a deactivated
user may come back. Orphan detection never blocks the deprovisioning itself: a failure there is
logged, not raised.

See [SCIM Provisioning](scim#deprovisioning) for the full mechanics and [Admin UI](admin-ui#user-and-group-lifecycle)
for the UI actions.

## Configuration

```bash
# Permission source evaluation order (default)
PERMISSION_SOURCE_ORDER=user,group,regex,group-regex

# Default permission when no explicit permission found (workspaces disabled)
DEFAULT_MLFLOW_PERMISSION=NO_PERMISSIONS
```

### Common Configurations

```bash
# Security-first: deny by default, require explicit grants
DEFAULT_MLFLOW_PERMISSION=NO_PERMISSIONS
PERMISSION_SOURCE_ORDER=user,group,regex,group-regex

# Group-priority: check group permissions first
PERMISSION_SOURCE_ORDER=group,user,group-regex,regex
DEFAULT_MLFLOW_PERMISSION=READ

# Regex-first: pattern-based permissions take priority
PERMISSION_SOURCE_ORDER=regex,group-regex,user,group
DEFAULT_MLFLOW_PERMISSION=READ
```

## Migrating to deny-by-default

> **The shipped `DEFAULT_MLFLOW_PERMISSION` changes from `MANAGE` to `NO_PERMISSIONS` in the next major version** ([#293](https://github.com/mlflow-oidc/mlflow-oidc-auth/issues/293)).

### What changes, and for whom

`DEFAULT_MLFLOW_PERMISSION` decides access when a resource has **no** user, group, regex or group-regex grant. Today it ships as `MANAGE`, so a fresh install is open by default: every authenticated user can read, edit and delete every experiment and registered model until grants exist.

You are affected only if **all** of the following hold:

- you do **not** set `DEFAULT_MLFLOW_PERMISSION` explicitly, **and**
- workspaces are disabled (`MLFLOW_ENABLE_WORKSPACES=false`), **and**
- some users reach resources through the fallback rather than through a grant

With workspaces enabled the global default is not used as a resource fallback at all — workspace permissions take that role — so workspace deployments are unaffected.

### Pinning current behaviour

If you want no change at all, set the value explicitly before upgrading:

```bash
DEFAULT_MLFLOW_PERMISSION=MANAGE
```

This is supported and will keep working. The change is to the *default*, not to the option.

### Migrating properly (recommended)

**1. Find out how much access is coming from the fallback.** Every permission decision made by the default is logged, and grants are warned about:

```
WARNING DEFAULT_MLFLOW_PERMISSION granted MANAGE on experiment=12 to alice
        because no explicit permission exists (1 such grants for experiment so far)
```

Warnings are throttled (occurrences 1, 10, 100, 1000, …), so treat them as a signal to investigate, not a count. Enable `DEBUG` logging to see every occurrence with its resource and user.

**2. Create the grants those users actually need.** For each resource that showed up, grant explicitly — to a user, a group, or a name-regex rule. Group and regex grants scale better than per-user ones:

```bash
# via the UI:  Permissions → Experiments / Models
# or the REST API under /oidc/api/
```

**3. Verify with the default already lowered**, in staging:

```bash
DEFAULT_MLFLOW_PERMISSION=NO_PERMISSIONS
```

Anything still reachable is reachable because of a real grant. Anything that breaks was relying on the fallback and needs a grant from step 2.

**4. Upgrade.** With the value set explicitly, or with the grants in place, the new default is a no-op for you.

### If you upgrade without migrating

Users lose access to resources they had no explicit grant for, and see `403`. Nothing is deleted and no permission records change — set `DEFAULT_MLFLOW_PERMISSION=MANAGE` to restore the previous behaviour immediately while you work through the steps above.

### Why this is changing

Open-by-default is a reasonable *adoption* choice — install the plugin and nothing breaks — but it is the wrong default for a plugin whose purpose is multi-tenant isolation. It also silently defeats `RESTRICT_RESOURCE_CREATION`: with a permissive default, that flag denies nothing (the plugin now warns at startup when this combination is configured).

## Examples

### Direct User Permission

```
User: alice
Resource: experiment_123
Sources checked (in PERMISSION_SOURCE_ORDER):
  1. user: EDIT permission found → stop
Result: EDIT
```

### Group Inheritance

```
User: bob (member of dev-team, qa-team)
Resource: experiment_456
Sources checked:
  1. user: no permission found
  2. group: dev-team has MANAGE, qa-team has READ → highest wins
Result: MANAGE
```

Where a membership came from does not affect resolution. A user can be in one group because
the directory put them there (SCIM), in another because their login's claims say so, and in a
third because an administrator added them. Each group grants what it grants. The source is
recorded on the membership only to decide who may remove it. See
[Row ownership](configuration#group-membership).

### Regex Pattern Match

```
User: charlie
Resource: prod-model-v1
Sources checked:
  1. user: no permission found
  2. group: no permission found
  3. regex: pattern "^prod-.*" → NO_PERMISSIONS (priority 1, matches first)
Result: NO_PERMISSIONS (access denied)
```

### Fallback to Default (Workspaces Disabled)

```
User: diana
Resource: new-experiment
Sources checked:
  1. user: not found
  2. group: not found
  3. regex: no matching patterns
  4. group-regex: no matching patterns
  5. Fallback: DEFAULT_MLFLOW_PERMISSION
Result: MANAGE (from default)
```

### Workspace Fallback (Workspaces Enabled)

```
User: diana
Resource: new-experiment (in workspace "data-team")
Diana has READ permission on workspace "data-team"
Sources checked:
  1. user: not found
  2. group: not found
  3. regex: no matching patterns
  4. group-regex: no matching patterns
  5. Workspace fallback: diana has READ on "data-team"
Result: READ (from workspace fallback)
```

## Resource Creation Authorization

By default, any authenticated user can create experiments and registered models — this matches upstream MLflow. Because the resource does not exist yet at creation time, the usual per-resource permission (keyed by experiment id or model name) cannot apply, so creation was historically unguarded.

Set `RESTRICT_RESOURCE_CREATION=true` to require **EDIT** (`can_update`) or higher to create a resource. Since the resource is new, only **name-based** sources are consulted:

1. `regex` — the user's own regex patterns matched against the new resource name
2. `group-regex` — the user's groups' regex patterns matched against the new resource name
3. Fallback when neither matches:
   - **Workspaces disabled** → the global `DEFAULT_MLFLOW_PERMISSION`
   - **Workspaces enabled** → the user's permission on the request workspace (deny if they have none)

> ⚠️ **The default `DEFAULT_MLFLOW_PERMISSION` is `MANAGE`, which grants `can_update`.** In a non-workspace deployment, enabling `RESTRICT_RESOURCE_CREATION` alone does **nothing** — a name that matches no regex falls back to `MANAGE` and creation is still allowed. To actually restrict creation you must either lower `DEFAULT_MLFLOW_PERMISSION` below `EDIT` (e.g. `NO_PERMISSIONS`) so only regex/group-regex matches can create, or rely on the workspace gate. Setting the flag without doing one of these gives a false sense of lockdown.

This closes a real gap in non-workspace deployments: with a project-prefix scheme like `<project>/<name>`, a user granted `^team-a/.*` could still create `team-b/whatever` (e.g. via a typo) and end up owning a resource they cannot subsequently access.

### Interaction with workspaces

When workspaces are enabled, creation is *also* subject to the workspace creation gate (workspace `MANAGE`, plus `OIDC_WORKSPACE_REQUIRE_CREATION_CONTEXT` / `OIDC_WORKSPACE_DENY_DEFAULT_CREATION`). The two checks compose as **AND** — a create must satisfy *both*. Enabling `RESTRICT_RESOURCE_CREATION` therefore never grants more than the workspace gate alone; it only ever adds restriction. If you run with workspaces, the workspace gate is the primary control and `RESTRICT_RESOURCE_CREATION` is optional.

### Affected endpoints

| Endpoint | Effect when restricted |
|----------|------------------------|
| `CreateExperiment` | Requires EDIT+ for the new experiment name |
| `CreateRegisteredModel` | Requires EDIT+ for the new model name |

Child resources (`CreateRun`, `CreateModelVersion`, …) are unaffected — they inherit permission from their parent.
