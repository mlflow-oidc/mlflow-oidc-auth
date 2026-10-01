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
| MCP Servers | `/mcp-servers` | List the MCP servers of the selected workspace you can manage (all for an admin) and manage their user and group permissions. MLflow 3.15+; see [MCP Server Registry](permissions#mcp-server-registry) |

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
| Groups | `/groups` | List all groups. Click a group to view/edit permissions for experiments, models, prompts, and gateways. Admins see member count and directory source, and can create a group by name up front (see below) |
| Service Accounts | `/service-accounts` | Manage service accounts and their permissions |

### Workspaces

These pages appear when `MLFLOW_ENABLE_WORKSPACES=true`:

| Page | Path | Description |
|------|------|-------------|
| Workspaces | `/workspaces` | List workspaces. Click to manage user/group workspace permissions |
| Workspace rules | `/workspace-rules` | Admin only. Rules that attach groups to workspaces by group name. See [Workspace rules](#workspace-rules) |

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
| User Profile | `/user` | View your profile, permissions, and manage your access tokens (see [Access token tabs](#access-token-tabs)) |

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
- **MCP Servers**: Direct permissions only (there are no regex patterns for MCP servers)

Regex pattern permissions are managed separately from direct permissions, with priority ordering.

### Access token tabs

Your own **User Profile** page (`/user`) has a **Tokens** tab: a table of your access tokens
(name, prefix — shown as "Carried over" for a secret from before this feature — created,
expires, last used, and status), a **+ Create token** button next to the search box, and a delete
action with a confirmation. Creating a token shows its plaintext **once** in a dedicated
dialog — copy it immediately, since it cannot be retrieved again. Tokens are meant for your own
interactive work (the MLflow client on a laptop or in a notebook): create one per device or
purpose, give it a short expiry, and delete it when you are done. For CI/CD, scheduled jobs and
services use a workload identity instead — see [Programmatic access](programmatic-access).

Admins see the same **Tokens** tab on a user's permission page and on a service account's
permission page, with the same table plus create, delete, and a **Revoke all tokens** action for
the leaked-token case. Issuing a token for a service account is the exception, for a tool that
can only send basic auth — see
[When an admin-issued token for a service account is acceptable](programmatic-access#when-an-admin-issued-token-for-a-service-account-is-acceptable). This replaces the older single "access token" block and its rotate modal,
which are gone.

## User and Group Lifecycle

Admins see lifecycle state on the Users and Groups pages that non-admins do not (both fall back
to the plain name list otherwise).

**Users** (`/users`): each row shows a **State** badge (Active/Inactive) and a **Managed by**
badge — Manual, SCIM, or OIDC · `<provider>` — naming the source that owns the row. A "Show
inactive" toggle above the table controls whether deactivated users are listed at all. Hovering a
row reveals a **Deactivate** or **Reactivate** action:

- **Deactivate** revokes the user's live sessions and deletes all of their access tokens
  immediately; their permission grants are kept, so reactivating restores access with no
  re-granting needed. Reactivation does not bring the deleted tokens back — the user creates new
  ones, or an admin issues one for a service account.
- **Reactivate** restores access; the user signs in again or is issued a new access token.
- **Sessions** opens the user's live sign-in sessions: a short id prefix, the provider, when it
  was opened and when it expires. **Revoke** ends one session and **Revoke all** ends every one,
  each after a confirmation; the list refreshes afterwards. The session is signed out on its next
  request. The account, its grants and its access tokens are not affected; use Deactivate for that.

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

A group otherwise exists only after one of its members has signed in, which blocks granting it a
permission ahead of time. The **+ Create group** button opens a dialog for a name and creates the
group immediately (issues #64, #201, #63) — click **Manage permissions** on the new row afterwards
to grant it access. The action is admin-only and idempotent: creating a name that already exists
(including one a directory already owns) succeeds without changing anything, so there is no way
to accidentally take over a SCIM-managed group's ownership from here.

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

## Workspace rules

The **Workspace rules** page (`/workspace-rules`) manages the rules described in
[Workspaces → Group rules](workspaces#group-rules). It is shown only to administrators, and only
when `MLFLOW_ENABLE_WORKSPACES=true`: the navigation entry is hidden otherwise, and the route sends a
non-admin to the access-denied page. This is cosmetic — the server refuses every rule request from a
non-admin and answers `404` while workspaces are off.

- **Rules table**: name, pattern, permission, mode (a **Report** or **Enforce** badge), whether the
  rule is enabled, and when it last changed. Rules are listed oldest first; when several match the
  same group and workspace, the oldest wins.
- **Create / edit**: name, group name pattern, permission, mode and enabled. The permission choices
  stop at the server's ceiling (`WORKSPACE_RULES_MAX_PERMISSION`); an existing rule above a lowered
  ceiling shows its permission marked as such, and saving the rule without touching it keeps it.
  New rules start in **Report** mode.
- **Rule builder**: next to the pattern, builds one by example — search for an existing group and
  the workspace it should get, and it writes the pattern (and a name, if none is set yet). Choose
  "Match every group with the same shape" to cover every group named like it, e.g. `team-acme-ds`
  and `acme` give `^team-(?P<ws>[a-z0-9-]+)-ds$`; otherwise the pattern matches that one group.
  The group's name must contain the workspace's name — a rule takes the workspace from the group
  name — so for any other pair the builder says so: grant that group on the workspace's page
  instead. The default workspace is not offered. The built pattern can still be edited and
  previewed before saving.

  | Group | Workspace | Every group of the same shape | Pattern written |
  |---|---|---|---|
  | `team-acme-ds` | `acme` | off | `^team-(?P<ws>acme)-ds$` — that group only |
  | `team-acme-ds` | `acme` | on | `^team-(?P<ws>[a-z0-9-]+)-ds$` — `team-globex-ds`, … too |
  | `partner:ml-acme` | `acme` | on | `^partner:ml-(?P<ws>[a-z0-9-]+)$` — the partner's `ml-*` groups |
  | `acme` | `acme` | off | `^(?P<ws>acme)$` |
  | `data-scientists` | `acme` | — | not built: grant the group on `acme`'s page instead |
- **Preview**: lists each existing group the pattern matches, its target workspace, and what
  enforcing the rule would do — grant, update, unchanged, remove, skip (with the reason, such as a
  manual grant or a missing workspace) or shadowed (by an older rule). Nothing is written. A new
  rule is previewed as a new rule would rank; unsaved changes to an existing rule keep that rule's
  precedence and its current grants. Preview is unavailable for an unsaved permission above the
  ceiling, since the server would refuse it; a saved rule above a lowered ceiling can still be
  previewed and shows its groups as skipped.
- **Delete**: asks for confirmation, then deletes the rule and every workspace permission it
  granted. Grants made by hand stay.

A server error, such as a pattern without the `(?P<ws>...)` group, is shown in the dialog as the
server worded it. If a rule is saved but its grants could not be updated (MLflow's workspace store
was unavailable), an error message says so; open the rule and save it again to retry. Group names and patterns are always
displayed as text.

The grants a rule creates appear on the workspace's page like any other group permission. Editing
one there turns it into a manual grant that no rule changes again.

## Workspace Picker

When workspaces are enabled, a workspace selector appears in the UI header. Switching workspaces:

- Automatically refreshes all data views (experiments, models, webhooks, trash)
- Updates the `X-MLFLOW-WORKSPACE` header for all API calls
- Persists the selected workspace in local storage
- Selects which workspace's grants the model, prompt and AI Gateway permission pages show and change.
  Those grants belong to one workspace ([details](workspaces#grants-on-models-prompts-and-gateway-resources)),
  and each of those pages — the matching tabs of a user or group, and your own User Page — names
  the workspace. With **All Workspaces** selected they show the `default` workspace's grants
  read-only: choose a workspace to add, change or remove one. Experiment grants are unaffected.
- A pattern (regex rule) applies in the workspace selected when it is created, or in every workspace
  under **All Workspaces**; the "Add New Regex Rule" dialog says which, and pattern lists show each
  pattern's workspace ([details](workspaces#pattern-regex-grants)).

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
