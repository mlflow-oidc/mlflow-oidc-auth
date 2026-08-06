# Admin UI

The plugin includes a React-based administration interface for managing permissions, users, groups, webhooks, and trash. Access it at `/oidc/ui/` on your MLflow server.

## Accessing the UI

After logging in via OIDC, navigate to:

```
https://your-mlflow-host/oidc/ui/
```

If `EXTEND_MLFLOW_MENU=true` (default), a link to the admin UI is also injected into MLflow's built-in navigation bar.

## Navigation

The sidebar organizes features into sections:

### Resources

| Page | Path | Description |
|------|------|-------------|
| Experiments | `/experiments` | List experiments with permission summaries. Click an experiment to manage its user and group permissions |
| Models | `/models` | List registered models with permission summaries |
| Prompts | `/prompts` | List prompts with permission summaries |

### AI Gateway

These pages appear when `OIDC_GEN_AI_GATEWAY_ENABLED=true` (default):

| Page | Path | Description |
|------|------|-------------|
| AI Endpoints | `/ai-gateway/ai-endpoints` | List gateway endpoints and manage their permissions |
| AI Secrets | `/ai-gateway/secrets` | List gateway secrets and manage their permissions |
| AI Models | `/ai-gateway/models` | List gateway model definitions and manage their permissions |

### Identity

| Page | Path | Description |
|------|------|-------------|
| Users | `/users` | List all users. Click a user to view/edit their experiment, model, prompt, and gateway permissions |
| Groups | `/groups` | List all groups. Click a group to view/edit permissions for experiments, models, prompts, and gateways |
| Service Accounts | `/service-accounts` | Manage service accounts and their permissions |

### Workspaces

These pages appear when `MLFLOW_ENABLE_WORKSPACES=true`:

| Page | Path | Description |
|------|------|-------------|
| Workspaces | `/workspaces` | List workspaces. Click to manage user/group workspace permissions |

### Admin Tools

These pages require admin privileges:

| Page | Path | Description |
|------|------|-------------|
| Trash | `/trash` | View and manage deleted experiments and runs. Restore or permanently delete |
| Webhooks | `/webhooks` | Create, edit, test, and delete webhooks |

### User

| Page | Path | Description |
|------|------|-------------|
| User Profile | `/user` | View your profile, permissions, and manage your access token |

## Managing Permissions

### Resource Permission View

When you click a resource (experiment, model, prompt, etc.), you see a detail view with:

- **Current permissions**: All user and group permissions for this resource
- **Permission kind**: Shows the source (`user`, `group`, `regex`, `group-regex`, `workspace` when applicable)
- **Add permission**: Grant access to a user or group
- **Edit permission**: Change the permission level
- **Delete permission**: Revoke access

### User/Group Permission View

When you click a user or group, you see their permissions across all resource types:

- **Experiments**: Direct and regex pattern permissions
- **Models**: Direct and regex pattern permissions
- **Prompts**: Direct and regex pattern permissions
- **AI Gateway Endpoints/Secrets/Models**: Direct and regex pattern permissions

Regex pattern permissions are managed separately from direct permissions, with priority ordering.

## Workspace Picker

When workspaces are enabled, a workspace selector appears in the UI header. Switching workspaces:

- Automatically refreshes all data views (experiments, models, webhooks, trash)
- Updates the `X-MLFLOW-WORKSPACE` header for all API calls
- Persists the selected workspace in local storage

## Search and Filtering

Resource list pages support search/filter functionality to quickly find specific experiments, models, users, or groups.

## Dark Mode

The UI includes a dark mode toggle accessible from the sidebar. The preference is stored in local storage.

## Runtime Configuration

The UI loads its configuration from the backend at startup via `GET /oidc/ui/config.json`. This includes:

- Whether AI Gateway features are enabled
- Whether workspaces are enabled
- The OIDC provider display name
- Feature flags that control which sidebar sections appear

No client-side configuration files are needed.
