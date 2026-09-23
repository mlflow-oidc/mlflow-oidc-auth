# SCIM Provisioning

The plugin serves a SCIM 2.0 endpoint ([RFC 7643](https://www.rfc-editor.org/rfc/rfc7643),
[RFC 7644](https://www.rfc-editor.org/rfc/rfc7644)) at `/scim/v2`. A directory (Microsoft Entra
ID, Okta, or a script) can use it to create users, keep their attributes current and, most
importantly, **deprovision** them: a user the directory deactivates loses every session and
token on their next request.

The `User` and `Group` resources are implemented. See [Groups](#groups) for group
membership and how it coexists with memberships that come from logins or administrators.

Nothing changes for a deployment that never issues a SCIM token: the endpoint accepts no other
credential.

## Tokens

SCIM clients authenticate with a dedicated bearer token issued by an administrator. It is not a
user credential:

- A SCIM token authenticates **only** on `/scim/v2`. It names no user, so every other endpoint
  rejects it.
- **Nothing else** authenticates on `/scim/v2`: not a browser session, not a user's access
  token, not an OIDC bearer token, and not an administrator's. The path is excluded from the
  normal authentication chain, and every route under it, including discovery and the fallback
  for unknown paths, requires the SCIM token.

Tokens look like `scim_<prefix>_<secret>`. The 8-character prefix is a non-secret lookup handle,
and the secret is 256 random bits. Only a hash is stored. The plaintext is shown **once**, in
the response that issues it.

```bash
# Issue (admin). The response contains "token": copy it into the directory now.
curl -u admin@example.com:$ADMIN_TOKEN -X POST https://mlflow.example.com/api/2.0/mlflow/scim/tokens \
  -H 'Content-Type: application/json' -d '{"name": "entra-prod", "expires_at": "2027-06-30T00:00:00Z"}'

# List (never returns hashes or plaintexts)
curl -u admin@example.com:$ADMIN_TOKEN https://mlflow.example.com/api/2.0/mlflow/scim/tokens

# Rotate: returns a new token; the old one keeps working for SCIM_TOKEN_ROTATION_OVERLAP_SECONDS
curl -u admin@example.com:$ADMIN_TOKEN -X POST https://mlflow.example.com/api/2.0/mlflow/scim/tokens/1/rotate

# Revoke immediately
curl -u admin@example.com:$ADMIN_TOKEN -X DELETE https://mlflow.example.com/api/2.0/mlflow/scim/tokens/1
```

**Rotation.** The replacement keeps the token's name and expiry. The old token is renamed
`<name> (rotated #<id>)` and expires after the overlap window (`SCIM_TOKEN_ROTATION_OVERLAP_SECONDS`,
default one hour), so you can paste the new token into the directory without a failed sync in
between. A revoked or expired token cannot be rotated.

**Rate limit.** Each token may make `SCIM_RATE_LIMIT_PER_MINUTE` requests per minute (default
600). Requests over the limit get `429`. The limit is kept **per process**: with N replicas, a
token can make up to N times the configured rate. It exists to stop a runaway sync from swamping
a process, not as a security boundary. If you need a shared limit, enforce it at your ingress.

**Failed authentication.** Requests without a valid token are limited to
`SCIM_AUTH_FAILURE_LIMIT_PER_MINUTE` failures per client IP per minute (default 60). Beyond that
they get `429` instead of `401`. A valid token from the same address is never refused by this
limit, so an attacker behind the same NAT cannot stop your sync. This limit is also kept per
process, and the client IP is the one `ProxyHeadersMiddleware` resolved: if `X-Forwarded-For`
is not restricted to `TRUSTED_PROXIES`, a client can rotate it. The limit reduces noise and CPU
load. It does not lock anyone out.

**Audit.** Every authenticated SCIM request emits a `scim.request` audit event with the token
name, method, path and response status. Unauthenticated requests emit at most one
`scim.auth_failed` event per client IP per minute. The event counts the failures in the window
that just closed (`detail.failures_in_previous_window`), so an anonymous flood cannot flood the
audit log. Token issue, rotation and revocation emit `scim_token.create`, `scim_token.rotate` and
`scim_token.revoke`. Plaintexts and presented credentials are never logged.

## Directory configuration

| Setting | Value |
|---|---|
| Tenant / base URL | `https://<your-mlflow-host>/scim/v2` |
| Authentication | Bearer token, the `scim_...` value issued above |
| Unique identifier | `userName`, which must match the username users sign in with (by default their email) |

### Identifiers

The SCIM `id` of a user is their **username**. `userName` is immutable through SCIM, so the id
is stable, as RFC 7643 §3.1 requires. `externalId` is stored and can be changed. It cannot serve
as the id because the client controls it. `/Users/{id}` resolves the **username only**. It
never falls back to an `externalId`, because one user's `externalId` could equal another
user's name and redirect a write. A client that knows only the `externalId` finds the user with
`GET /Users?filter=externalId eq "..."` and then addresses it by the returned `id`.

A new `userName` may not contain `/`, `?`, `#` or `%`, because it becomes a `/Users/{id}` path
segment. `POST` refuses it with `400 invalidValue`. A row that already holds one of those
characters (a hand-made one, say) can still be found by filter and addressed at its
percent-encoded `meta.location`.

The directory's `externalId` is stored on the user row (`users.external_id`, unique when
present). SCIM does **not** write a `user_identities` row: a directory is not a sign-in
provider, and the provisioning policy treats any provider already bound to an account as its
owner. A `("scim", externalId)` identity would therefore make every SCIM user's first OIDC
sign-in look like a second provider trying to claim the account, and refuse it. Without that
row, the user's first OIDC sign-in lands on the SCIM-created account:

- through the default provider, by username;
- through an email-bound provider, by verified email within `allowed_email_domains`.

It then binds that provider's `(provider, sub)` identity as usual.

### Supported operations

| Method | Path | Notes |
|---|---|---|
| GET | `/ServiceProviderConfig`, `/ResourceTypes[/User\|/Group]`, `/Schemas[/<urn>]` | Discovery |
| GET | `/Users` | `filter` supports only `userName eq "..."` and `externalId eq "..."`. `startIndex` is 1-based; `count` defaults to 100, max 200 |
| GET | `/Users/{id}` | |
| POST | `/Users` | `409 uniqueness` if the userName or externalId is taken. An omitted `active` means `true` |
| PUT | `/Users/{id}` | Replaces `displayName` and `externalId`; an omitted `externalId` is cleared. An omitted `active` **keeps the current state**, so a PUT never reactivates a deprovisioned user by leaving the attribute out |
| PATCH | `/Users/{id}` | `add` / `replace` on `active`, `displayName`, `externalId`, `name.*`, `userName` (unchanged only). Paths may be URN-qualified; a path-less op takes an object |
| DELETE | `/Users/{id}` | Hard delete. See below |

Stored attributes are `userName`, `displayName` (or `name.formatted`, or given and family name
joined), `externalId` and `active`. `POST` and `PUT` ignore other attributes, as RFC 7644
permits. `PATCH` refuses any other path, such as `emails[...]`, with `400 invalidPath`, and
applies **none** of the request's operations, so a directory never believes a write landed when
it did not. If your directory sends such paths, remove those attribute mappings.
`givenName` and `familyName` are accepted and not stored. All changes from one request are
applied in a single transaction. If any part is refused (for example, an `externalId` another
user already holds), nothing is applied, including a deactivation in the same request.

**`userName` rules.** Surrounding whitespace is stripped. A `userName` is refused with
`400 invalidValue` when it is:

- empty or longer than 255 characters;
- contains control or other non-printing characters (newline, NUL, zero-width space);
- not already in its NFKC-normalised, case-folded form.

The last rule makes look-alikes collide. A fullwidth or ligature spelling of `alice@example.com`
is refused instead of becoming a second account, and a name that differs only in case is the
same account. Usernames are stored in lower case, the form every login looks up.

**Filters.** A malformed filter value (bad escape, raw control character, lone surrogate) is
`400 invalidFilter`.

Rules that SCIM cannot change:

- **SCIM never grants administrator.** Users created by SCIM are ordinary users, and `roles` or
  any `is_admin` attribute is ignored. Admin status still comes from `OIDC_ADMIN_GROUP_NAME`.
- **Service accounts are invisible to SCIM.** They are not listed, and any request that names
  one gets a 404.
- **Last administrator.** Deactivating or deleting the only active administrator is refused with
  a SCIM `400`. The check locks the active-admin rows, so two concurrent requests cannot each
  remove "the other" admin.
- **Blast radius of a token.** Under the default `MANAGED_BY_ENFORCEMENT=report`, a SCIM token
  can deactivate, modify or delete any non-service-account user except the last active
  administrator. Writes outside SCIM's own rows are applied and recorded as
  `user.ownership_conflict`. Under `enforce`, SCIM can change only the rows it owns and
  hand-made non-administrators. Treat a SCIM token like an admin credential: set an expiry,
  rotate it, and revoke it at once if it leaks.

### Ownership

SCIM writes as `scim` ([Row ownership](configuration#row-ownership)).

**What SCIM owns.** SCIM takes ownership of a row (`managed_by='scim'`, audited as
`user.ownership_claimed`) only when it provisions it:

- when it creates the user (`POST`);
- when it first binds an `externalId` to a hand-made, non-administrator row that had none. This
  is how a directory adopts accounts created before SCIM was set up.

No other SCIM write changes ownership.

**Rows SCIM does not own.** Any other SCIM write to such a row goes through the ownership guard
like any other writer:

| Row owner | `report` (default) | `enforce` |
|---|---|---|
| `scim` | written | written |
| `manual`, not an admin | written | written |
| `manual` **administrator** | written; `user.ownership_conflict` recorded; stays `manual` | **refused** (`409 mutability`) |
| `oidc:*` / `saml:*` / other | written; conflict recorded; ownership unchanged | **refused** (`409 mutability`) |

A hand-made administrator is never claimed. Under `enforce`, SCIM cannot modify, deactivate or
delete one. Otherwise the break-glass admin would be only as safe as the SCIM token.

A user created by a first SSO sign-in is owned by `manual`, not by the provider, so SCIM may
adopt such a user by setting an `externalId` unless the sign-in granted them admin. The
`oidc:*` / `saml:*` row above is reserved for provider-owned rows and is not written today.

**SSO sign-in to a SCIM-owned account.** Signing in is not an ownership change. An `oidc:*` or
`saml:*` provider signing a user in may write a `scim`-owned row, including under `enforce`, but
it may change only `is_admin`. The sign-in path writes `is_admin` only for a provider with
`admin_source: claims`. Group membership follows the provider's `group_sync` policy as usual.
A sign-in can never change `managed_by`, `active`, the credential or the service-account flag on
a SCIM-owned row. A provider writing a row another *provider* owns is still a foreign write.

Before turning on `enforce`, make sure the directory owns the rows it should manage. Either let
it bind `externalId`s, or hand rows over with `mlflow-oidc db reconcile-ownership`.

`DELETE` goes through the same guard, inside the delete's own transaction. A refused delete
removes nothing and hands nothing over to `ORPHAN_FALLBACK_PRINCIPAL`.

## Groups

`/scim/v2/Groups` provisions groups and their membership. Group membership is what carries
permissions ([Permissions](permissions)), so this is where the directory's access decisions take effect.

### Identifiers

A group's SCIM `id` is its **name**, as a user's is their username. `displayName` is therefore
immutable through SCIM: a `PUT` or `PATCH` that changes it gets `400 mutability`. To rename a
group, create a new one. Group names are **case-sensitive**, because they are compared with IdP
group claims exactly as the IdP sends them. A new `displayName` follows the same rules as a
`userName`, except that it is not case-folded. It may not be empty or longer than 255
characters, contain control characters, or contain `/`, `?`, `#` or `%`.

`externalId` is stored on the group (`groups.external_id`, unique when present). As for users,
it is **not** an id. `/Groups/{id}` resolves the name only, and a client that knows only the
`externalId` uses `GET /Groups?filter=externalId eq "..."`.

`POST` for a name that already exists gets `409 uniqueness`, even when a login or an
administrator created the group. Entra and Okta look a group up by `displayName` before creating
it, and then manage the one they find through `PATCH`/`PUT`.

Members are **users only**. A member is `{"value": "<user id>"}`, and `display`, `$ref` and
`type` are accepted. A `type` of `Group` (a nested group) is refused with `400 invalidValue`. So
is a member that names no user. In both cases the whole request is refused and nothing is
applied. Service accounts are not visible: they are never listed as members and cannot be
added, and a `PUT` never removes them.

### Operations

| Method | Path | Notes |
|---|---|---|
| GET | `/Groups` | `filter` supports only `displayName eq "..."` and `externalId eq "..."`. `startIndex` / `count` as for users. `excludedAttributes=members` omits members |
| GET | `/Groups/{id}` | `excludedAttributes=members` supported |
| POST | `/Groups` | `displayName` required. `externalId` and `members` optional |
| PUT | `/Groups/{id}` | Okta's shape. `displayName` must be unchanged. `externalId` is replaced, and an absent one is cleared. `members` replaces the membership as a sync (below). **An omitted `members` leaves membership unchanged**, so a PUT carrying only attributes never empties a group |
| PATCH | `/Groups/{id}` | See below |
| DELETE | `/Groups/{id}` | Removes the group, its memberships and every permission granted to it. See [Deleting a group](#deleting-a-group) |

**PATCH.** Operations apply in order, in one transaction. `op` is case-insensitive
(`Add`/`Remove`/`Replace`, as Entra sends them), and paths may be URN-qualified.

| Operation | Shape | Sent by |
|---|---|---|
| Add members | `{"op": "add", "path": "members", "value": [{"value": "<id>"}, ...]}` | Entra, Okta |
| Remove one member | `{"op": "remove", "path": "members[value eq \"<id>\"]"}` | Entra |
| Remove listed members | `{"op": "remove", "path": "members", "value": [{"value": "<id>"}]}` | Entra |
| Remove every member | `{"op": "remove", "path": "members"}` | |
| Replace members | `{"op": "replace", "path": "members", "value": [...]}` | |
| Set or clear `externalId` | `add` / `replace` / `remove` on `externalId` | |
| No path | `{"op": "replace", "value": {"displayName": ..., "externalId": ..., "members": [...]}}` | Entra |

`displayName` (and `id`) may be re-asserted unchanged. Anything else gets `400` and **none** of
the request's operations are applied: any other path (`invalidPath`), a filter other than
`members[value eq "..."]`, a filtered path with `add` or `replace`, a sub-attribute after the
filter such as `members[value eq "x"].display`, or another `op`. Removing a user who is not a
member does nothing and is not an error.

### Membership ownership

Every membership SCIM writes is owned by `scim`, per row. So a user can hold, at once,
memberships granted by the directory, by an administrator (`manual`) and by a login's claims
(`oidc:<provider>` / `saml:<provider>`). Permission resolution does not care who granted a
membership, and each one grants what its group grants. Ownership decides only who may
**remove** it ([Row ownership](configuration#group-membership)):

| Membership owner | SCIM adds | SCIM removes under `report` (default) | SCIM removes under `enforce` |
|---|---|---|---|
| `scim` | yes | yes | yes |
| `manual` | yes (already a member: unchanged) | yes | yes, except a hand-made administrator's |
| `oidc:*` / `saml:*` | yes (already a member: unchanged) | yes, recorded as `user.ownership_conflict` | **refused** |

Adding a user who is already a member through another source changes nothing: the membership
keeps its owner.

How a refusal shows depends on the operation:

- A targeted removal (`PATCH` `remove`) is refused with `409 mutability`, and nothing in the
  request is applied.
- A replacement (`PUT` with `members`, `PATCH` `replace members`) is a sync. SCIM's own and
  unowned memberships that are not in the list are removed. A membership another source owns is
  **left in place** under `enforce`, and the request succeeds. The response lists the membership
  as it actually is. Refusing the whole sync would stop the directory from ever updating that
  group again.

Every refused or permitted cross-source removal is audited as `user.ownership_conflict`, with
`detail.operation: "membership.remove"` and `detail.group`.

A login works the same way from the other side. Under `enforce`, an `authoritative` login leaves
SCIM's memberships in place. Under `report` it removes them as it always has, and records each
one. **If the directory and an `authoritative` provider share users, run `enforce`, or set that
provider's `group_sync_mode` to `additive`.** Otherwise, under `report`, every sign-in removes
the directory's memberships and the next sync adds them back.

SCIM membership never grants administrator rights, even in a group named in
`OIDC_ADMIN_GROUP_NAME`: admin status comes only from a login's claims.

### Deleting a group

`DELETE /Groups/{id}` removes the group, **every** membership in it, and every permission
granted to the group (experiments, models and prompts, scorers, gateway resources, workspaces,
regex grants included). If you recreate a group with the same name, it starts with no grants.

When the group holds memberships SCIM does not own, including hand-made (`manual`) ones:

- Under `enforce`, the delete is refused with `409 mutability` and nothing is removed. Deleting
  the group would take it away from those members too.
- Under `report`, it proceeds and records each such membership as `user.ownership_conflict`
  (`detail.operation: "group.delete"`).

A group delete is never refused because it would leave resources without a manager.

### Audit

On top of the `scim.request` event every SCIM request emits, group writes emit `group.create`
(members), `group.members_changed` (`added`, `removed`, and `kept`, the rows the guard left in
place), `group.external_id_set` and `group.delete` (`members_removed`).

Errors use the RFC 7644 §3.12 shape with content type `application/scim+json`:

```json
{"schemas": ["urn:ietf:params:scim:api:messages:2.0:Error"], "status": "400", "scimType": "invalidPath", "detail": "..."}
```

## Deprovisioning

Directories normally deactivate rather than delete. For example, Entra sends
`PATCH active:false`. When `active: false` (`PATCH` or `PUT`) deactivates an active user, in a
single transaction:

1. `users.active` is set to false, and the auth middleware refuses the user on every
   authentication path from their next request on.
2. Every live server-side session for the user is revoked (`session.revoked` audit event).
3. The user's access token (basic-auth secret) is replaced with an undisclosed, already-expired
   value. Reactivation therefore never revives a credential issued before deprovisioning.

Sending `active: false` again for a user who is already inactive changes nothing. The
credential is not rewritten on every sync, and the ownership guard does not see a credential
write.

The account row and **every permission grant are kept**. `active: true` restores access with no
further action from an administrator. The user signs in again, or is issued a new access token
through the normal self-service path. Each transition emits `user.deactivated` or
`user.reactivated` with `detail.source = "scim"`.

`DELETE` is a hard delete: the user's grants, group memberships, identities and sessions are
removed. Use it for the rarer "gone for good" case.

### Orphaned resources

On deactivation and on delete (through SCIM or the admin API), the plugin looks for resources
where the departing user is the **last holder of `MANAGE`**. That means no other *active* user
holds `MANAGE` directly, and no group holding `MANAGE` has another active member. It checks
experiments, registered models and prompts, scorers, gateway endpoints, model definitions and
secrets, and workspaces. It emits one `resource.orphaned` audit event per resource, with
`resource_type`, `resource_id` and `detail.user`. Regex grants are not resolved against resource
names, and administrators are not counted: an administrator can always recover a resource.

If `ORPHAN_FALLBACK_PRINCIPAL` is set, a hard delete first grants that user `MANAGE` on each
orphaned resource (`detail.transferred_to` on the event). The fallback must be an existing,
active, non-service-account user other than the one being deleted. Otherwise the hand-over is
skipped with a warning and orphans are only reported. Deactivation never transfers, because a
deactivated user may come back.

The hand-over runs **inside the delete's own transaction**, before the cascade. A delete that is
refused, such as for the last active administrator, rolls the hand-over back with it, and
`resource.orphaned` events are emitted only after the delete has committed.

Orphan detection and transfer **never block deprovisioning**. They run under a savepoint, a
failure is logged, and the deactivation or delete proceeds without them.

### Retention

`USER_RETENTION_DAYS` is reserved for a future job that purges long-deactivated users. It
defaults to `0` (never), and nothing reads it yet.

## Admin API for lifecycle state

For the admin UI:

- `GET /api/2.0/mlflow/users/details` lists users with `active` and `managed_by`.
- `PATCH /api/2.0/mlflow/users/{username}/active` deactivates or reactivates a user with the
  same effects as above (`detail.source = "admin"`). A SCIM-managed user under `enforce` needs
  `"admin_override": true`.
- `DELETE /api/2.0/mlflow/users` hard-deletes a user through the same ownership guard. A
  SCIM-managed user under `enforce` needs `"admin_override": true` here as well, so an
  administrator refused a deactivation cannot hard-delete the user instead without it.

See the [API Reference](api-reference#scim).
