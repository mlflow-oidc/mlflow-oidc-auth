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
- `SearchLoggedModels` — removes logged models whose parent experiment is unreadable
- `ListGatewayEndpoints` — removes unreadable gateway endpoints
- `ListGatewaySecretInfos` — removes unreadable gateway secrets
- `ListGatewayModelDefinitions` — removes unreadable model definitions
- `ListWorkspaces` — removes workspaces the user has no READ permission for

The filtering preserves MLflow's pagination contract — the system continues fetching additional pages until the requested `max_results` is satisfied or no more results exist.

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
- All workspace-isolated resources (experiments, models, webhooks, trash) are automatically scoped to the active workspace

## Configuration

```bash
# Permission source evaluation order (default)
PERMISSION_SOURCE_ORDER=user,group,regex,group-regex

# Default permission when no explicit permission found (workspaces disabled)
DEFAULT_MLFLOW_PERMISSION=MANAGE
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
