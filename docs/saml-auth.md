# SAML authentication

Let people sign in to MLflow through a SAML 2.0 identity provider — ADFS, Entra ID, Okta, Ping,
Shibboleth, Keycloak — alongside or instead of OIDC. The plugin is a SAML **service provider
(SP)**: it sends the browser to your IdP with an AuthnRequest, validates the signed Response the
IdP posts back, and opens the same server-side session an OIDC login would.

**SAML is browser-only.** It has no bearer token: an assertion is posted once, by a browser, and
consumed. Anything that is not a browser — the MLflow Python SDK, the CLI, a CI job, a pod — keeps
authenticating the way it does today: an OIDC bearer token, a [Kubernetes service-account
token](kubernetes-auth), or a username and access token. A SAML provider never validates an
`Authorization` header, and nothing about it changes how those are checked.

## Installing

SAML support is an optional extra:

```bash
pip install "mlflow-oidc-auth[saml]"
```

It pulls in [python3-saml](https://github.com/SAML-Toolkits/python3-saml) and
[python-xmlsec](https://github.com/xmlsec/python-xmlsec). Both publish binary wheels for Linux
(manylinux), macOS and Windows on the supported CPython versions, so a wheel install needs **no
compiler and no `libxmlsec1` headers**. If pip falls back to building `xmlsec` from source — an
unusual platform or Python — it needs `libxmlsec1-dev` and `pkg-config` (Debian/Ubuntu) or
`libxmlsec1` from Homebrew.

Without the extra the plugin starts and works exactly as before. A `type: saml` provider is
dropped at startup with the reason logged (`type 'saml' requires the [saml] extra to be
installed`) and never appears on the login page. The check imports the library rather than
looking for the package, so an `xmlsec` whose native library cannot load counts as missing too.

## Configuring the provider

A SAML provider is an entry in `AUTH_PROVIDERS` / `AUTH_PROVIDERS_FILE`:

```json
{
  "id": "corp-saml",
  "type": "saml",
  "display_name": "Corporate SSO",
  "entity_id": "https://mlflow.example.com/saml/corp-saml",
  "idp_entity_id": "https://sts.example.com/adfs/services/trust",
  "idp_sso_url": "https://sts.example.com/adfs/ls/",
  "idp_slo_url": "https://sts.example.com/adfs/ls/",
  "idp_x509_cert": "MIIC8DCCAdigAwIBAgIQ...",
  "attribute_username": "email",
  "attribute_groups": "groups",
  "provisioning": "jit",
  "admin_source": "none"
}
```

Three values are required, and each is something every assertion is checked against:

- **`entity_id`** — this SP's entity id. Every assertion must name it in an
  `AudienceRestriction`; one with no audience at all is refused, even though the SAML library
  would accept it. Any stable URI works, as long as it is the one registered at the IdP.
- **`idp_entity_id`** — the IdP's entity id. The `Issuer` of the Response and of the assertion
  must equal it.
- **`idp_x509_cert`** — the IdP's signing certificate, as PEM or as the bare base64 from its
  metadata. A list is accepted for a rotation: a signature verifying against any of them passes.
  It may be omitted when `idp_metadata_url` supplies it (below).

`idp_sso_url` (the IdP's HTTP-Redirect SingleSignOnService) is required too, unless the metadata
supplies it. `idp_sso_url`, `idp_slo_url` and `idp_metadata_url` must be `https`.

The full field list, with defaults, is in [Configuration](configuration#saml-provider-fields).
Fields that configure bearer-token validation — `audience`, `issuer`, `discovery_url`,
`client_id`, `allowed_algorithms`, `allow_tokens_without_expiry` and the Kubernetes key fields —
are refused on a SAML entry rather than ignored, and the SAML fields are refused on every other
type. The id `default` is refused for a SAML entry: it belongs to the legacy OIDC provider,
which may adopt existing accounts by name. `identity_binding: email` is refused as well: SAML has no equivalent of `email_verified`,
so an email-bound SAML login could only work by trusting an attribute the user may be able to
edit at the IdP.

### What to register at the IdP

The plugin publishes SP metadata per provider, unauthenticated, at:

```
https://<mlflow>/saml/metadata/<id>
```

Most IdPs can import it directly. If yours wants the values by hand:

| IdP setting | Value |
|---|---|
| Entity ID / Identifier / Audience | your `entity_id` |
| ACS / Reply URL (HTTP-POST) | `https://<mlflow>/callback/<id>` |
| Single Logout URL (HTTP-Redirect) | `https://<mlflow>/slo/<id>` |
| NameID format | `name_id_format` (default `urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress`) |
| Signing | sign the assertion (default), or the response with `want_response_signed: true` |

The origin in those URLs comes from `OIDC_REDIRECT_URI` when it is set (its scheme, host and the
path above `/callback`), and otherwise from the incoming request. **Set `OIDC_REDIRECT_URI` in
production**: the ACS URL is what a Response's `Destination` and `Recipient` are checked
against, and deriving it from the request leaves it resting on the `Host` header.

### Getting the IdP's details

The IdP publishes all of it in its federation metadata:

| IdP | Metadata URL |
|---|---|
| ADFS | `https://<adfs>/FederationMetadata/2007-06/FederationMetadata.xml` |
| Entra ID | `https://login.microsoftonline.com/<tenant>/federationmetadata/2007-06/federationmetadata.xml?appid=<app-id>` |
| Okta | Applications → your app → Sign On → *Metadata URL* |
| Keycloak | `https://<keycloak>/realms/<realm>/protocol/saml/descriptor` |

Either copy `entityID`, the HTTP-Redirect `SingleSignOnService` / `SingleLogoutService`
locations and the signing `X509Certificate` into the entry, or point `idp_metadata_url` at the
document and let the plugin read it once at startup:

```json
{
  "id": "okta-saml",
  "type": "saml",
  "entity_id": "https://mlflow.example.com/saml/okta",
  "idp_entity_id": "http://www.okta.com/exk1abcd",
  "idp_metadata_url": "https://example.okta.com/app/exk1abcd/sso/saml/metadata"
}
```

The fetch has a 10-second timeout, a 1 MiB limit and does not follow redirects. The metadata must
describe `idp_entity_id` — `idp_entity_id` stays required so the document cannot choose which IdP
you trust. Values written in the entry win; the metadata only fills what is missing. If the fetch
fails the provider is **dropped** with the reason logged, and the rest of the registry is
unaffected. The certificate is read over TLS and trusted as delivered, so the URL must be one you
would trust to hand you the IdP's signing key; pinning `idp_x509_cert` explicitly avoids the
dependency, and a restart is what picks up a rotated certificate either way.

### Signing requests

Unsigned AuthnRequests are the default and are what most IdPs expect. To sign AuthnRequests,
LogoutRequests and LogoutResponses, give the SP a key pair:

```json
{
  "sp_x509_cert": "-----BEGIN CERTIFICATE-----\n...",
  "sp_private_key_file": "/var/run/secrets/mlflow/saml-sp.key",
  "sign_requests": true
}
```

`sp_private_key` takes the PEM inline instead of `sp_private_key_file` — one or the other. The key
must be an unencrypted RSA key that matches `sp_x509_cert`; a mismatch is refused at startup. The
key never appears in a log line, an error or a repr, and the metadata endpoint publishes only
the certificate. Signing is RSA-SHA256 with SHA-256 digests; SHA-1 signatures from the IdP are
refused.

## How a login works

1. The login page lists the provider (`GET /providers` returns it with `"type": "saml"` and
   `login_url: /login/<id>`).
2. `GET /login/<id>` records the attempt as an `auth_state` row — the same single-use,
   15-minute table OIDC logins use — and redirects to `idp_sso_url` with an AuthnRequest whose
   `ID` is derived from the row and whose `RelayState` is the row's key. With the
   [browser binding](#browser-binding) on, it also sets a nonce cookie and stores the nonce's hash
   on the row.
3. The IdP authenticates the user and auto-posts a Response to `POST /callback/<id>`.
4. The ACS, in order:
   - consumes the `RelayState` row. Unknown, expired, already used, or created for a
     *different* provider → `400` (audited as `auth.saml_relaystate_rejected`);
   - checks the [browser binding](#browser-binding): the nonce cookie must hash to what the
     consumed row recorded. Missing, or belonging to another attempt → `400`
     (`auth.saml_binding_rejected`). The cookie is cleared whatever the outcome;
   - validates the Response: signature against `idp_x509_cert`, `Issuer`, `Destination`,
     `Recipient`, audience, `NotBefore`/`NotOnOrAfter` with `clock_skew_seconds`, and that
     `InResponseTo` is the AuthnRequest from step 2 — on the Response *and* on the signed
     assertion's bearer `SubjectConfirmationData`, whose `Recipient` must equal this ACS exactly. An unsolicited Response is refused —
     **IdP-initiated SSO is not supported**, because nothing here asked for that assertion and it
     is exactly what an injected one looks like. Failures → `400`
     (`auth.saml_response_rejected`);
   - records the assertion `ID` in `saml_assertions` under a unique index. A second use of the
     same assertion → `400` (`auth.saml_replay_rejected`). An assertion with no `NotOnOrAfter`
     anywhere is refused, since it could never leave the replay table;
   - refuses a **deactivated** account (for example one SCIM set `active: false`) before any
     write: no row update, no session, no cookie, audited as `auth.denied_inactive`. The same
     check applies to OIDC logins;
   - provisions the user through the same policy as an OIDC login, opens a server-side session
     holding the NameID and `SessionIndex`, sets the cookie, and audits `auth.login` with
     `{"method": "saml", "provider": "<id>"}`.

Every refusal answers with the same fixed body; the reason goes to the server log.

### SameSite

The ACS is a cross-site POST from the IdP. Under the default `SESSION_COOKIE_SAMESITE=lax` the
browser does **not** send MLflow's cookie with it — and it does not need to. The login is tied to
its attempt through `RelayState` alone, and the session cookie is set fresh on the ACS response,
which browsers accept on a top-level navigation whatever its SameSite attribute. **Do not relax
`SESSION_COOKIE_SAMESITE` to `none` for SAML.**

### Browser binding

`RelayState` proves a Response answers *some* live attempt, not that the browser delivering it
started that attempt. Without more, someone who makes a victim's browser post *their own* valid
Response (with their own fresh `RelayState`) signs the victim in as themselves — login CSRF.

So `GET /login/<id>` also sets a cookie carrying a random 256-bit nonce:

- `HttpOnly; Secure; SameSite=None`, `Path=/callback/<id>` (the ACS, under any mount prefix),
  `Max-Age=600` — only the ACS ever receives it, and only for ten minutes;
- one cookie per attempt (its name is derived from the `RelayState`), so logins started in two
  tabs do not overwrite each other;
- only its SHA-256 is stored, on the `auth_state` row. The nonce is never stored or logged.

The ACS, after consuming the row named by `RelayState`, requires the cookie's hash to equal the
row's, and refuses otherwise before the Response is even parsed. The row is spent either way, and
the cookie is cleared on every outcome. `SameSite=None` is what lets this one cookie ride the
cross-site POST; the session cookie keeps its own `SameSite` and is still never read at the ACS.

`Secure` cookies are only returned over https, so the binding follows `SAML_LOGIN_BINDING`:

| Value | Behaviour |
|---|---|
| `auto` (default) | On exactly when `SESSION_COOKIE_SECURE=true`. Off otherwise — plain-http development would refuse every login — with a startup warning that SAML logins are not browser-bound |
| `on` | Forced on even with `SESSION_COOKIE_SECURE=false`, with a startup warning. For http test rigs on loopback (browsers treat `localhost`/`127.0.0.1` as secure contexts, so the `Secure` cookie still comes back); on any other plain-http host every SAML login is refused |
| `off` | Never bound. Only if something in front of MLflow strips the cookie and you accept the login-CSRF risk |

An attempt recorded with a binding needs its cookie even if the switch is turned off mid-flight,
and while the binding is on an attempt recorded without one is refused — logins in flight across
such a restart fail once and succeed on retry. Production deployments serve https and set
`SESSION_COOKIE_SECURE=true`, which turns the binding on with no further configuration.

## Single logout

Single logout uses the **HTTP-Redirect binding only**, in both directions. `/slo/<id>` accepts
`GET` and answers `POST` with `405`, and the SP metadata advertises only an HTTP-Redirect
`SingleLogoutService`. The reason is that the SAML library verifies logout-message signatures
only on the redirect binding. A POST-bound LogoutRequest could never validate, and a POST-bound
LogoutResponse would be accepted with no signature check. Configure the IdP to use
HTTP-Redirect for single logout.

### Starting from MLflow

`GET /logout` on a session opened by a SAML provider:

1. revokes the session row and clears the cookie, and audits `auth.logout` — **before anything is
   sent to the IdP**;
2. if the provider has `idp_slo_url`, redirects to it with a LogoutRequest carrying the session's
   NameID and `SessionIndex`, correlated through a fresh `auth_state` row.

Whatever then happens at the IdP — it is down, it refuses, the user closes the tab — nothing live
is left in MLflow: a copied cookie stops working at step 1. If the LogoutRequest cannot be built,
the user lands on the login page, still logged out. When the IdP answers at `/slo/<id>` with a
LogoutResponse to our request, the user lands on the login page; a response that does not answer
our request is a `400`. A SAML session is never sent to an OIDC provider's end-session endpoint.

### Starting from the IdP

The IdP may send a LogoutRequest to `GET /slo/<id>` (HTTP-Redirect binding) when the user signs
out elsewhere. It must be **signed** by the IdP's certificate, name the IdP as `Issuer`, and
carry a `Destination` exactly equal to this provider's `/slo/<id>` URL. The library alone would
accept any URL that starts with it, so a request meant for `/slo/<id>-eu` (another provider
sharing the IdP's certificate) would otherwise validate. An unsigned or mis-signed request, or
one with the wrong or no `Destination`, is a `400` and revokes nothing
(`auth.slo_request_rejected`), since otherwise any page could log users out with a link.

A valid request revokes the user's sessions **opened by that provider** — the one whose
`SessionIndex` matches, or all of them when the request lists none. Sessions the same user
opened through OIDC or another provider are untouched. The user is found through the
`(provider, NameID)` binding made at login. MLflow then redirects to `idp_slo_url` with a
LogoutResponse (signed when `sign_requests` is on), and audits `auth.slo_idp_initiated` with the
number of sessions revoked. If a revocation fails, whatever could be revoked is, and the answer
is a `400` rather than a success the IdP would believe.

`/slo/<id>` requires `idp_slo_url`: without one there is nowhere to send the LogoutResponse, and
requests are refused.

Each LogoutRequest is **single-use**: its `ID` is recorded in the same replay table as
assertions before anything is revoked, so a signed URL leaked from browser history or a proxy log
and replayed later is a `400` (`auth.slo_replay_rejected`) and ends nothing — in particular not
sessions opened since. A request without `NotOnOrAfter` must have an `IssueInstant` no older than
five minutes plus `clock_skew_seconds`. The one exception: if revocation fails, the `ID` is
released again before the `400` goes back, so the IdP's retry of the same request is processed
instead of being refused as a replay.

## What gets created

SAML logins provision through the same policy as OIDC ones:

- **Identity.** The user is bound to `(provider id, NameID)` on first login. Later logins match on
  that binding, not on any attribute. Prefer a persistent NameID
  (`urn:oasis:names:tc:SAML:2.0:nameid-format:persistent`) or an immutable email; a NameID that
  changes is a new identity.
- **Username.** The first value of `attribute_username` (default `email`), falling back to the
  NameID. It names the account; it does not identify it — a name already bound to another
  identity is refused, never taken over.
- **Display name.** `attribute_display_name` (default `displayName`), falling back to the
  username.
- **Groups.** `attribute_groups` (default `groups`). The login gate is the same as for OIDC: the
  user must be in `OIDC_GROUP_NAME` or, where `admin_source` allows it, `OIDC_ADMIN_GROUP_NAME`.
  Groups from any provider other than `default` are stored namespaced as `<id>:<group>`, and
  `group_sync` / `group_sync_mode` apply as for any provider.
- **Administrators.** Only when the entry sets `admin_source: claims`; the default for any
  provider but `default` is `none`.
- **Provisioning.** `provisioning: jit` creates users at first login; `scim` and `none` require
  the account to exist already (for example through [SCIM](scim)).
- **Workspaces.** With `MLFLOW_ENABLE_WORKSPACES` and no `OIDC_WORKSPACE_DETECTION_PLUGIN`, an
  attribute named `OIDC_WORKSPACE_CLAIM_NAME` assigns workspaces as the claim does for OIDC. When
  a plugin *is* configured it is the only source of membership; it reads an OAuth access token,
  which a SAML login does not have, so SAML logins are assigned no workspaces (grant them
  explicitly). `OIDC_GROUP_DETECTION_PLUGIN` likewise does not run for SAML logins.

The session lasts `SESSION_COOKIE_MAX_AGE_SECONDS`, or until the assertion's
`SessionNotOnOrAfter` if the IdP set one — after which the user signs in again (SAML has no
refresh).

## Housekeeping

`saml_assertions` gains one row per SAML login, kept until that assertion could no longer
validate. `mlflow-oidc db prune-sessions --url <db>` deletes expired rows along with expired
sessions; run it from cron.

## Troubleshooting

The browser only ever sees `SAML sign-in failed`. The server log names the reason:

| Log says | Usually means |
|---|---|
| `Signature validation failed` | `idp_x509_cert` is not the IdP's current signing certificate (rotation?) |
| `The Assertion of the Response is not signed` | the IdP signs only the Response — set `want_response_signed: true` and `want_assertions_signed: false`, or change the IdP |
| `is not a valid audience` / `does not name this SP` | the IdP's audience / identifier differs from `entity_id` |
| `The response was received at ... instead of ...` | the ACS URL registered at the IdP differs from the one MLflow derives — set `OIDC_REDIRECT_URI` |
| `RelayState names no live login attempt` | the login took longer than 15 minutes, was replayed, or began at a different provider |
| `did not start this login attempt` | the binding cookie did not arrive: the login took more than 10 minutes, the browser blocks third-party-context cookies for this site, it is plain http on a non-loopback host with `SAML_LOGIN_BINDING=on` — or the Response really was delivered by a different browser |
| `unsolicited or mismatched InResponseTo` | the user started at the IdP's portal (IdP-initiated SSO is refused) — start from MLflow's login page |
| `Found an Attribute element with duplicated Name` | the IdP sends one attribute per value — Keycloak's default `role_list` mapper does, one `Role` per role. Turn on its *Single Role Attribute*, or remove the `role_list` client scope from the SAML client |
| `Conditions NotOnOrAfter beyond the allowed clock skew` | clocks differ; fix NTP, or raise `clock_skew_seconds` (max 300) |
