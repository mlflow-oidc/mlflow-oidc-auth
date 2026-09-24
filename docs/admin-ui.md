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
| Users | `/users` | List all users. Click a user to view/edit their experiment, model, prompt, and gateway permissions. Admins see lifecycle state and can deactivate/reactivate (see [User and group lifecycle](#user-and-group-lifecycle)) |
| Groups | `/groups` | List all groups. Click a group to view/edit permissions for experiments, models, prompts, and gateways. Admins see member count and directory source |
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
| SCIM | `/scim` | Manage SCIM provisioning tokens. See [SCIM page](#scim-page) |

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

## User and Group Lifecycle

Admins see lifecycle state on the Users and Groups pages that non-admins do not (both fall back
to the plain name list otherwise).

**Users** (`/users`): each row shows a **State** badge (Active/Inactive) and a **Managed by**
badge — Manual, SCIM, or OIDC · `<provider>` — naming the source that owns the row. A "Show
inactive" toggle above the table controls whether deactivated users are listed at all. Hovering a
row reveals a **Deactivate** or **Reactivate** action:

- **Deactivate** revokes the user's live sessions and access token immediately; their permission
  grants are kept, so reactivating restores access with no re-granting needed.
- **Reactivate** restores access; the user signs in again or is issued a new access token.
- **Sessions** opens the user's live sign-in sessions: a short id prefix, the provider, when it
  was opened and when it expires. **Revoke** ends one session and **Revoke all** ends every one,
  each after a confirmation; the list refreshes afterwards. The session is signed out on its next
  request. The account, its grants and its access token are not affected; use Deactivate for that.

If the target account is directory-managed (SCIM or OIDC), the deactivate dialog shows an
**"Override ownership guard"** switch, since a later directory sync could otherwise overwrite the
change. Under [row ownership enforcement](configuration#row-ownership) `enforce`, leaving the
switch off and deactivating a directory-owned account is refused; switching it on sends
`admin_override: true` with the request and proceeds. The override is always audited when sent,
whatever `MANAGED_BY_ENFORCEMENT` is set to. See [De-provisioning](permissions#de-provisioning)
for what deactivation and reactivation do underneath, and [SCIM
Provisioning](scim#admin-api-for-lifecycle-state) for the API this UI calls.

**Groups** (`/groups`): each row shows a **Members** count and a **Source** badge (SCIM when the
group carries a directory `external_id`, Manual otherwise). Groups have no deactivate action —
membership and permissions are managed the same way regardless of source.

## SCIM Page

The **SCIM** page (`/scim`, admin-only) manages the directory provisioning integration described
in [SCIM Provisioning](scim):

- **Provisioning endpoint**: the full `/scim/v2` URL for this deployment, with a copy button, to
  paste into the identity provider's SCIM configuration.
- **Tokens table**: every issued token with its name, prefix, creation time, creator, last-used
  time, expiry, and status (Active, Expiring — within 14 days of its expiry, or Revoked).
- **Create token**: opens a dialog for a name and optional expiry, then shows the plaintext
  **once** in a dedicated dialog — copy it immediately, since it cannot be retrieved again.
- **Rotate**: issues a replacement token (shown once, same as creation) while the old token keeps
  working for `SCIM_TOKEN_ROTATION_OVERLAP_SECONDS`, so the directory sync does not fail while the
  new value is being pasted in.
- **Revoke**: disables a token immediately. Rotate and revoke are unavailable for a token that is
  already revoked.
- **Provisioning status**: **Healthy** when a SCIM request succeeded within
  `SCIM_ACTIVITY_HEALTHY_WINDOW_SECONDS` (24 hours by default), **Unhealthy** when none did, and
  **Never used** before any directory has connected. Next to it: the last success, the last error
  with its SCIM message, requests and failures in the last 24 hours, and rejected tokens. A table
  shows the same per token, including its last-used time.
- **Recent activity**: the latest SCIM requests with time, token, method, resource (the route and
  the SCIM id), status, outcome and error. Failed requests are highlighted. Filter by outcome, and
  **Load more** pages further back, as far as `SCIM_ACTIVITY_RETENTION_DAYS` keeps. See
  [Provisioning status and activity](scim#provisioning-status-and-activity) for what is recorded.

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
