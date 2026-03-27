# Permission System and Hierarchy

## Permission Levels

The system defines five permission levels with a hierarchical priority system:

### 1. READ Permission
- **Priority**: 1 (lowest hierarchy level)
- **Capabilities**:
  - `can_read: true`
  - `can_use: false`
  - `can_update: false`
  - `can_delete: false`
  - `can_manage: false`
- **Description**: Allows read-only access to resources

### 2. USE Permission
- **Priority**: 2
- **Capabilities**:
  - `can_read: true`
  - `can_use: true`
  - `can_update: false`
  - `can_delete: false`
  - `can_manage: false`
- **Description**: Allows reading and using resources (e.g., invoking gateway endpoints)

### 3. EDIT Permission
- **Priority**: 3
- **Capabilities**:
  - `can_read: true`
  - `can_use: true`
  - `can_update: true`
  - `can_delete: false`
  - `can_manage: false`
- **Description**: Allows reading, using, and updating resources

### 4. MANAGE Permission
- **Priority**: 4 (highest hierarchy level)
- **Capabilities**:
  - `can_read: true`
  - `can_use: true`
  - `can_update: true`
  - `can_delete: true`
  - `can_manage: true`
- **Description**: Full control over resources

### 5. NO_PERMISSIONS
- **Priority**: 100 (special case — explicit denial)
- **Capabilities**:
  - `can_read: false`
  - `can_use: false`
  - `can_update: false`
  - `can_delete: false`
  - `can_manage: false`
- **Description**: Explicit denial of access. This is a valid permission object (not the same as having no permission record at all). When assigned, the user is actively denied access to the resource regardless of other permission sources.

## Permission Source Order

The `PERMISSION_SOURCE_ORDER` configuration controls the order in which permission sources are evaluated. The system checks each source in the specified order and uses the first permission found. If no explicit permission is found in any source, the system falls back to the default permission.

### Default Source Order
```
PERMISSION_SOURCE_ORDER=user,group,regex,group-regex
```

### Source Types

1. **`user`**: Direct user permissions for specific resources
2. **`group`**: Group-based permissions (users inherit from their groups)
3. **`regex`**: User-specific regex pattern permissions
4. **`group-regex`**: Group-based regex pattern permissions (users inherit regex permissions from their groups)

## Default Permission Behavior

When no explicit permission is found in any configured source, the system falls back to the default permission.

### Configuration
```bash
DEFAULT_MLFLOW_PERMISSION=MANAGE
```

### Default Values
- **Default**: `MANAGE`
- **Effect**: Users have full access to all resources unless explicitly restricted
- **Alternatives**: Can be set to `READ`, `USE`, `EDIT`, or `NO_PERMISSIONS`


### Resolution Steps

1. **Iterate through sources** in `PERMISSION_SOURCE_ORDER`
2. **Query each source** for the specific resource and user
3. **Return first found permission** with source information
4. **Workspace fallback** (when `MLFLOW_ENABLE_WORKSPACES=true`): If no explicit resource permission exists, use the user's workspace permission as the baseline (see [Workspace Permissions as Resource Fallback](#workspace-permissions-as-resource-fallback))
5. **Apply default permission** if no explicit permission exists and workspaces are disabled
6. **Log permission source** for debugging and audit trails


### Example Priority Resolution

```python
# Users belong to groups with different permissions
Group A: experiment_123 -> READ (priority 1)
Group B: experiment_123 -> MANAGE (priority 4)

# Result: MANAGE permission (higher hierarchy level wins)
```

## Regex Permission System

Regex permissions allow pattern-based access control using Python regular expressions. Instead of assigning permissions to individual resources, you can define regex patterns that match resource names and assign a permission level to each pattern.

Regex permissions come in two variants:
- **User regex permissions**: Assigned directly to a user
- **Group regex permissions**: Assigned to a group (inherited by all group members)

Both are evaluated as part of the `PERMISSION_SOURCE_ORDER` chain (via the `regex` and `group-regex` source types).

### Pattern Syntax
The system uses Python regular expression syntax:
- `.*` - Matches any experiment/model name
- `^prod-.*` - Matches names starting with "prod-"
- `.*-test$` - Matches names ending with "-test"
- `^(dev|test|staging)-.*` - Matches names starting with specific prefixes

### Priority System
- **Lower numbers** have higher priority
- **Priority 1** patterns are checked first
- **The first matching pattern** determines permission

### Example Regex Permissions

```python
# User regex permissions for experiments
Priority 1: "^prod-.*" -> NO_PERMISSIONS
Priority 2: "^dev-.*" -> MANAGE
Priority 3: ".*" -> READ

# For experiment "dev-ml-model":
# 1. Check "^prod-.*" -> No match
# 2. Check "^dev-.*" -> Match! -> MANAGE permission
```

## Gateway Permissions

Gateways are now a first-class resource in the permission system. Permission sources (user, group, regex, group-regex) are evaluated in the same order as other resources. Use the same permission levels (READ, USE, EDIT, MANAGE) to control gateway discovery and proxy operations. The plugin exposes APIs under `/mlflow/permissions/gateways` for administering gateway permissions.

## Workspace Permissions

Workspaces provide multi-tenant resource isolation and are gated by the `MLFLOW_ENABLE_WORKSPACES` feature flag (default `False`). When enabled, all workspace access requires explicit permission grants — there are no implicit grants for any workspace, including the "default" workspace.

### How Workspace Permissions Work

Workspace permissions use the same `Permission` levels as resource permissions (READ, USE, EDIT, MANAGE, NO_PERMISSIONS) and the same resolution chain configured via `PERMISSION_SOURCE_ORDER`.

| Permission       | Workspace Access                                          |
|------------------|-----------------------------------------------------------|
| `READ`           | Can view workspace and its resources in search/list results |
| `USE`            | Can use workspace resources                                |
| `EDIT`           | Can modify workspace resources                             |
| `MANAGE`         | Full control: create experiments/models in the workspace, manage workspace permissions |
| `NO_PERMISSIONS` | Explicit denial — workspace is hidden from all results     |

### Workspace Permissions as Resource Fallback

Workspace permissions serve a dual role:

1. **Workspace-level access control** — they gate access to workspace API endpoints (create, list, update, delete workspaces) and filter which workspaces appear in search results.

2. **Resource-level fallback** — when a user accesses a resource (experiment, model, prompt) inside a workspace and **no explicit resource-level permission** is found (no user, group, regex, or group-regex permission for that specific resource), the system falls back to the user's workspace permission as the baseline access level.

#### Resource Permission Resolution with Workspaces

When workspaces are enabled, the full resolution chain for a resource is:

```
1. Resource-level sources (PERMISSION_SOURCE_ORDER):
   user → group → regex → group-regex
2. If no resource-level permission found → workspace permission fallback
3. If no workspace permission found → NO_PERMISSIONS (denied)
```

Note that when workspaces are enabled and a resource has no explicit permission, the system does **not** fall back to `DEFAULT_MLFLOW_PERMISSION`. Instead, it uses the workspace permission. This ensures that workspace boundaries are enforced — a user cannot access resources in a workspace they have no permission for, even if `DEFAULT_MLFLOW_PERMISSION` is set to `MANAGE`.

#### Example: Workspace Fallback in Action

```
User: alice
Workspace: team-alpha (alice has EDIT workspace permission)
Resource: experiment_789 (in team-alpha workspace)

Resolution:
- user permission for experiment_789: Not found
- group permission for experiment_789: Not found
- regex match for experiment_789: Not found
- group-regex match for experiment_789: Not found
- Workspace fallback: alice has EDIT on team-alpha → EDIT
Result: EDIT permission (from workspace fallback)
```

```
User: alice
Workspace: team-beta (alice has no workspace permission)
Resource: experiment_999 (in team-beta workspace)

Resolution:
- user permission for experiment_999: Not found
- group permission for experiment_999: Not found
- regex match for experiment_999: Not found
- group-regex match for experiment_999: Not found
- Workspace fallback: alice has no permission on team-beta → NO_PERMISSIONS
Result: Access denied
```

#### Important Implications

- Granting a user `MANAGE` on a workspace means they can manage **all resources** in that workspace that don't have more specific permissions — not just the workspace itself.
- To restrict access to specific resources within a workspace, assign explicit resource-level permissions. Resource-level permissions always take priority over the workspace fallback.
- The workspace fallback only applies when `MLFLOW_ENABLE_WORKSPACES=true`. When workspaces are disabled, the system uses `DEFAULT_MLFLOW_PERMISSION` as the fallback.

### Enforcement Points

1. **Workspace API endpoints**: `GetWorkspace`, `UpdateWorkspace`, `DeleteWorkspace`, `CreateWorkspace`, `ListWorkspaces` are gated by workspace-level permission checks
2. **Resource creation gating**: `CreateExperiment` and `CreateRegisteredModel` require `MANAGE` permission on the target workspace
3. **Search/list filtering**: Results from `SearchExperiments`, `SearchRegisteredModels`, `SearchLoggedModels`, and `ListWorkspaces` are filtered to only include resources in workspaces the user can read
4. **Permission management API**: Workspace permission CRUD endpoints require `MANAGE` on the workspace

### Key Difference: `NO_PERMISSIONS` vs No Record

- **`NO_PERMISSIONS` assigned**: The user is explicitly denied — `can_read` is `False`. The workspace is hidden from all results.
- **No permission record**: No explicit permission exists for the user/workspace pair. The workspace is also inaccessible (there is no implicit default grant for workspaces).

Admin users bypass all workspace permission checks.

### Configuration

```bash
# Enable workspace support (default: false)
MLFLOW_ENABLE_WORKSPACES=true

# Permission auto-assigned to new users during OIDC login (default: NO_PERMISSIONS)
OIDC_WORKSPACE_DEFAULT_PERMISSION=NO_PERMISSIONS

# Workspace permission cache settings
WORKSPACE_CACHE_MAX_SIZE=1024
WORKSPACE_CACHE_TTL_SECONDS=300
```

## Configuration

### Environment Variables

```bash
# Permission source evaluation order
PERMISSION_SOURCE_ORDER="user,group,regex,group-regex"

# Default permission when no explicit permission found
DEFAULT_MLFLOW_PERMISSION="MANAGE"
```

### Alternative Configurations

```bash
# Security-first approach - deny by default
PERMISSION_SOURCE_ORDER="user,group,regex,group-regex"
DEFAULT_MLFLOW_PERMISSION="NO_PERMISSIONS"

# Group-priority approach
PERMISSION_SOURCE_ORDER="group,user,group-regex,regex"
DEFAULT_MLFLOW_PERMISSION="READ"

# Regex-first approach
PERMISSION_SOURCE_ORDER="regex,group-regex,user,group"
DEFAULT_MLFLOW_PERMISSION="READ"
```

## Examples

### Example 1: User with Direct Permission
```
User: alice
Resource: experiment_123
Sources:
- user: EDIT permission found
- group: (not checked - user permission found first)
Result: EDIT permission from user source
```

### Example 2: Group Inheritance
```
User: bob (member of dev-team, qa-team)
Resource: experiment_456
Sources:
- user: No permission found
- group: dev-team has MANAGE, qa-team has READ
Result: MANAGE permission (MANAGE hierarchy level 4 beats READ hierarchy level 1)
```

### Example 3: Regex Pattern Matching
```
User: charlie
Resource: prod-model-v1
Sources:
- user: No permission found
- group: No permission found
- regex: Pattern "^prod-.*" -> NO_PERMISSIONS
Result: NO_PERMISSIONS from regex source
```

### Example 4: Fallback to Default (Workspaces Disabled)
```
User: diana
Resource: new-experiment
Workspaces: disabled
Sources:
- user: No permission found
- group: No permission found
- regex: No matching patterns
- group-regex: No matching patterns
Result: MANAGE permission from fallback (DEFAULT_MLFLOW_PERMISSION)
```

### Example 5: Workspace Fallback (Workspaces Enabled)
```
User: diana
Resource: new-experiment (in workspace "data-team")
Workspaces: enabled (diana has READ on "data-team")
Sources:
- user: No permission found
- group: No permission found
- regex: No matching patterns
- group-regex: No matching patterns
- workspace fallback: diana has READ on "data-team"
Result: READ permission from workspace fallback
```
