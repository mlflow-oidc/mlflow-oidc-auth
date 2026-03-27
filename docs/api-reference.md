# API Reference

The plugin exposes ~198 REST API endpoints for authentication, permission management, workspace management, webhooks, and trash operations. This reference covers the plugin's own endpoints — MLflow's native tracking/registry API is not documented here (see [MLflow docs](https://mlflow.org/docs/latest/rest-api.html)).

## Authentication

All endpoints except health probes, login/callback, and static files require authentication. The plugin supports three authentication methods (tried in order):

1. **Basic Auth**: `Authorization: Basic base64(username:password)`
2. **JWT Bearer Token**: `Authorization: Bearer <jwt_token>`
3. **Session Cookie**: Set automatically after OIDC login

When workspaces are enabled, include the `X-MLFLOW-WORKSPACE` header to specify the active workspace.

## Permission Levels

Request/response bodies reference these permission values:

| Value | Description |
|-------|-------------|
| `READ` | Read-only access |
| `USE` | Read + use (e.g., invoke endpoints) |
| `EDIT` | Read + use + update |
| `MANAGE` | Full control including delete and permission management |
| `NO_PERMISSIONS` | Explicit denial |

---

## Auth Endpoints

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/login` | Public | Initiate OIDC login flow (redirects to OIDC provider) |
| GET | `/callback` | Public | Handle OIDC callback (exchange code for tokens, establish session) |
| GET | `/logout` | Public | Clear session and redirect to OIDC provider logout |
| GET | `/auth/status` | Public | Return current authentication status |

**`GET /auth/status` response:**
```json
{
  "authenticated": true,
  "username": "alice@example.com",
  "provider": "oidc"
}
```

---

## Health Endpoints

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/health` | Public | Basic health check |
| GET | `/health/live` | Public | Liveness probe |
| GET | `/health/ready` | Public | Readiness probe (checks OIDC + database) |
| GET | `/health/startup` | Public | Startup probe (checks OIDC initialization) |

**`GET /health/ready` response (200):**
```json
{
  "status": "ready",
  "checks": {
    "oidc": "ok",
    "database": "ok"
  }
}
```

---

## User Management

Base path: `/api/2.0/mlflow/users`

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/api/2.0/mlflow/users` | Authenticated | List users. Query param `service=true` to include service accounts |
| POST | `/api/2.0/mlflow/users` | Admin | Create a new user |
| DELETE | `/api/2.0/mlflow/users` | Admin | Delete a user |
| GET | `/api/2.0/mlflow/users/current` | Authenticated | Get current user's profile |
| GET | `/api/2.0/mlflow/users/{username}` | Admin | Get a specific user's profile |
| PATCH | `/api/2.0/mlflow/users/access-token` | Authenticated | Create/rotate access token |

**`POST /api/2.0/mlflow/users` request:**
```json
{
  "username": "alice@example.com",
  "display_name": "Alice",
  "is_admin": false
}
```

**`GET /api/2.0/mlflow/users/current` response:**
```json
{
  "username": "alice@example.com",
  "display_name": "Alice",
  "is_admin": false,
  "groups": ["mlflow-users", "data-team"],
  "experiment_permissions": [...],
  "registered_model_permissions": [...]
}
```

---

## Resource Permission Listing

These endpoints list resources with their permission summaries. Used by the admin UI for the permission management views.

### Experiments

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/api/2.0/mlflow/permissions/experiments` | Authenticated | List experiments with permission summary |
| GET | `/api/2.0/mlflow/permissions/experiments/{id}/users` | Experiment MANAGE | List user permissions for an experiment |
| GET | `/api/2.0/mlflow/permissions/experiments/{id}/groups` | Experiment MANAGE | List group permissions for an experiment |

### Registered Models

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/api/2.0/mlflow/permissions/registered-models` | Authenticated | List models with permission summary |
| GET | `/api/2.0/mlflow/permissions/registered-models/{name}/users` | Model MANAGE | List user permissions for a model |
| GET | `/api/2.0/mlflow/permissions/registered-models/{name}/groups` | Model MANAGE | List group permissions for a model |

### Prompts

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/api/2.0/mlflow/permissions/prompts` | Authenticated | List prompts with permission summary |
| GET | `/api/2.0/mlflow/permissions/prompts/{name}/users` | Prompt MANAGE | List user permissions for a prompt |
| GET | `/api/2.0/mlflow/permissions/prompts/{name}/groups` | Prompt MANAGE | List group permissions for a prompt |

### Scorers

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/api/3.0/mlflow/permissions/scorers/{experiment_id}` | Authenticated | List scorers for an experiment |
| GET | `/api/3.0/mlflow/permissions/scorers/{experiment_id}/{name}/users` | Scorer MANAGE | List user permissions |
| GET | `/api/3.0/mlflow/permissions/scorers/{experiment_id}/{name}/groups` | Scorer MANAGE | List group permissions |

### Gateway Endpoints

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/api/2.0/mlflow/permissions/gateways/endpoints` | Authenticated | List gateway endpoints |
| GET | `/api/2.0/mlflow/permissions/gateways/endpoints/{name}/users` | Endpoint MANAGE | List user permissions |
| GET | `/api/2.0/mlflow/permissions/gateways/endpoints/{name}/groups` | Endpoint MANAGE | List group permissions |

### Gateway Secrets

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/api/2.0/mlflow/permissions/gateways/secrets` | Authenticated | List gateway secrets |
| GET | `/api/2.0/mlflow/permissions/gateways/secrets/{name}/users` | Secret MANAGE | List user permissions |
| GET | `/api/2.0/mlflow/permissions/gateways/secrets/{name}/groups` | Secret MANAGE | List group permissions |

### Gateway Model Definitions

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/api/2.0/mlflow/permissions/gateways/model-definitions` | Authenticated | List model definitions |
| GET | `/api/2.0/mlflow/permissions/gateways/model-definitions/{name}/users` | Model Def MANAGE | List user permissions |
| GET | `/api/2.0/mlflow/permissions/gateways/model-definitions/{name}/groups` | Model Def MANAGE | List group permissions |

---

## User Permission CRUD

Base path: `/api/2.0/mlflow/permissions/users/{username}`

These endpoints manage per-user permissions for each resource type. The pattern is identical for all resource types.

### Direct Permissions

For each resource type, the following CRUD operations are available:

| Method | Path Pattern | Auth | Purpose |
|--------|-------------|------|---------|
| GET | `/{username}/{resource-type}` | Authenticated | List all permissions for this user |
| POST | `/{username}/{resource-type}/{resource-id}` | Resource MANAGE | Grant permission |
| GET | `/{username}/{resource-type}/{resource-id}` | Resource MANAGE | Get specific permission |
| PATCH | `/{username}/{resource-type}/{resource-id}` | Resource MANAGE | Update permission |
| DELETE | `/{username}/{resource-type}/{resource-id}` | Resource MANAGE | Revoke permission |

**Resource types and paths:**

| Resource | Path Segment | Resource ID |
|----------|-------------|-------------|
| Experiments | `experiments` | `{experiment_id}` |
| Registered Models | `registered-models` | `{name}` |
| Prompts | `prompts` | `{name}` |
| Scorers | `scorers` | `{experiment_id}/{scorer_name}` |
| Gateway Endpoints | `gateways/endpoints` | `{name}` |
| Gateway Secrets | `gateways/secrets` | `{name}` |
| Gateway Model Definitions | `gateways/model-definitions` | `{name}` |

**Request body (POST/PATCH):**
```json
{
  "permission": "EDIT"
}
```

### Regex Pattern Permissions

For each resource type, regex pattern permissions are also available:

| Method | Path Pattern | Auth | Purpose |
|--------|-------------|------|---------|
| POST | `/{username}/{resource-type}-patterns` | Admin | Create regex pattern permission |
| GET | `/{username}/{resource-type}-patterns` | Authenticated | List regex pattern permissions |
| GET | `/{username}/{resource-type}-patterns/{id}` | Admin | Get specific pattern permission |
| PATCH | `/{username}/{resource-type}-patterns/{id}` | Admin | Update pattern permission |
| DELETE | `/{username}/{resource-type}-patterns/{id}` | Admin | Delete pattern permission |

**Request body (POST/PATCH):**
```json
{
  "pattern": "^prod-.*",
  "permission": "READ",
  "priority": 1
}
```

**Pattern path segments:** `experiment-patterns`, `registered-models-patterns`, `prompts-patterns`, `scorer-patterns`, `gateways/endpoints-patterns`, `gateways/secrets-patterns`, `gateways/model-definitions-patterns`

**Total: 70 user permission endpoints** (7 resource types x 10 operations each)

---

## Group Permission CRUD

Base path: `/api/2.0/mlflow/permissions/groups`

### Group Listing

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/api/2.0/mlflow/permissions/groups` | Authenticated | List all groups |
| GET | `/api/2.0/mlflow/permissions/groups/{group_name}/users` | Admin | List group members |

### Group Direct Permissions

Same CRUD pattern as user permissions, but scoped to groups:

| Method | Path Pattern | Auth | Purpose |
|--------|-------------|------|---------|
| GET | `/{group_name}/{resource-type}` | Authenticated | List group's permissions |
| POST | `/{group_name}/{resource-type}/{resource-id}` | Resource MANAGE or Admin | Grant permission |
| PATCH | `/{group_name}/{resource-type}/{resource-id}` | Resource MANAGE or Admin | Update permission |
| DELETE | `/{group_name}/{resource-type}/{resource-id}` | Resource MANAGE or Admin | Revoke permission |

### Group Regex Pattern Permissions

| Method | Path Pattern | Auth | Purpose |
|--------|-------------|------|---------|
| POST | `/{group_name}/{resource-type}-patterns` | Admin | Create regex pattern permission |
| GET | `/{group_name}/{resource-type}-patterns` | Authenticated | List regex pattern permissions |
| GET | `/{group_name}/{resource-type}-patterns/{id}` | Admin | Get specific pattern permission |
| PATCH | `/{group_name}/{resource-type}-patterns/{id}` | Admin | Update pattern permission |
| DELETE | `/{group_name}/{resource-type}-patterns/{id}` | Admin | Delete pattern permission |

**Total: 69 group permission endpoints** (2 group-level + 7 resource types x ~9.5 operations each)

---

## Trash Management

Base path: `/oidc/trash`

All trash endpoints require **admin** permissions.

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/oidc/trash/experiments` | List deleted experiments |
| GET | `/oidc/trash/runs` | List deleted runs. Query: `experiment_ids`, `older_than` |
| POST | `/oidc/trash/cleanup` | Permanently delete trashed items. Query: `older_than`, `run_ids`, `experiment_ids` |
| POST | `/oidc/trash/experiments/{experiment_id}/restore` | Restore a deleted experiment |
| POST | `/oidc/trash/runs/{run_id}/restore` | Restore a deleted run |

When workspaces are enabled, trash operations are automatically scoped to the active workspace.

---

## Webhook Management

Base path: `/oidc/webhook`

All webhook endpoints require **admin** permissions.

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/oidc/webhook` | Create a webhook |
| GET | `/oidc/webhook` | List webhooks. Query: `max_results`, `page_token` |
| GET | `/oidc/webhook/{webhook_id}` | Get webhook details |
| PUT | `/oidc/webhook/{webhook_id}` | Update a webhook |
| DELETE | `/oidc/webhook/{webhook_id}` | Delete a webhook |
| POST | `/oidc/webhook/{webhook_id}/test` | Send a test event to the webhook |

**`POST /oidc/webhook` request:**
```json
{
  "url": "https://hooks.example.com/webhook",
  "events": ["MODEL_VERSION_CREATED", "MODEL_VERSION_TRANSITIONED_STAGE"],
  "description": "Notify on model promotion"
}
```

When workspaces are enabled, webhooks are automatically scoped to the active workspace.

---

## Workspace Endpoints

These endpoints are only available when `MLFLOW_ENABLE_WORKSPACES=true`.

### Workspace CRUD

Base path: `/api/3.0/mlflow/workspaces/crud`

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | `/api/3.0/mlflow/workspaces/crud` | Admin | Create workspace |
| GET | `/api/3.0/mlflow/workspaces/crud` | Authenticated | List workspaces (filtered by permission) |
| GET | `/api/3.0/mlflow/workspaces/crud/{workspace}` | Workspace READ | Get workspace details |
| PATCH | `/api/3.0/mlflow/workspaces/crud/{workspace}` | Workspace MANAGE | Update workspace |
| DELETE | `/api/3.0/mlflow/workspaces/crud/{workspace}` | Workspace MANAGE | Delete workspace |

### Workspace User Permissions

Base path: `/api/3.0/mlflow/permissions/workspaces/{workspace}`

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `.../users` | Workspace READ | List user permissions for workspace |
| POST | `.../users` | Workspace MANAGE | Grant user workspace permission |
| PATCH | `.../users/{username}` | Workspace MANAGE | Update user workspace permission |
| DELETE | `.../users/{username}` | Workspace MANAGE | Revoke user workspace permission |

### Workspace Group Permissions

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `.../groups` | Workspace READ | List group permissions for workspace |
| POST | `.../groups` | Workspace MANAGE | Grant group workspace permission |
| PATCH | `.../groups/{group_name}` | Workspace MANAGE | Update group workspace permission |
| DELETE | `.../groups/{group_name}` | Workspace MANAGE | Revoke group workspace permission |

### Workspace Regex Permissions (Admin Only)

Base path: `/api/3.0/mlflow/permissions/workspaces/regex`

| Method | Path | Purpose |
|--------|------|---------|
| POST | `.../regex/user` | Create user regex workspace permission |
| GET | `.../regex/user` | List user regex workspace permissions |
| PATCH | `.../regex/user/{id}` | Update user regex workspace permission |
| DELETE | `.../regex/user/{id}` | Delete user regex workspace permission |
| POST | `.../regex/group` | Create group regex workspace permission |
| GET | `.../regex/group` | List group regex workspace permissions |
| PATCH | `.../regex/group/{id}` | Update group regex workspace permission |
| DELETE | `.../regex/group/{id}` | Delete group regex workspace permission |

---

## Admin UI

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/oidc/ui/config.json` | Authenticated | Runtime configuration for the React SPA |
| GET | `/oidc/ui/` | Public | Serve the admin UI (React SPA) |
| GET | `/oidc/ui/{path}` | Public | Serve static files or SPA fallback |

---

## Error Responses

All API errors follow this format:

```json
{
  "error_code": "RESOURCE_DOES_NOT_EXIST",
  "message": "User 'unknown@example.com' not found"
}
```

Common HTTP status codes:

| Status | Meaning |
|--------|---------|
| 401 | Authentication required (no valid credentials) |
| 403 | Forbidden (authenticated but insufficient permissions) |
| 404 | Resource not found |
| 409 | Conflict (resource already exists) |
| 503 | Service unavailable (health check failure) |
