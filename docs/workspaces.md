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
- To restrict access to specific resources within a workspace, assign explicit resource-level permissions (they always take priority over the workspace fallback)
- The workspace fallback only applies when `MLFLOW_ENABLE_WORKSPACES=true`

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

## API Reference

### Workspace CRUD

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | `/api/3.0/mlflow/workspaces/crud` | Admin | Create workspace |
| GET | `/api/3.0/mlflow/workspaces/crud` | Authenticated | List workspaces (filtered by permission) |
| GET | `/api/3.0/mlflow/workspaces/crud/{workspace}` | Workspace READ | Get workspace details |
| PATCH | `/api/3.0/mlflow/workspaces/crud/{workspace}` | Workspace MANAGE | Update workspace |
| DELETE | `/api/3.0/mlflow/workspaces/crud/{workspace}` | Workspace MANAGE | Delete workspace |

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

See the full [API Reference](api-reference) for request/response schemas.
