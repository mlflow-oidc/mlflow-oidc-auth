# Troubleshooting

## Login fails after returning from the identity provider

**Symptom.** Signing in at the identity provider works, but back on MLflow the login fails. The log
shows `OIDC token exchange error`, and the error may name `mismatching_state` ("CSRF Warning! State
not equal in request and response").

**Why.** The login is bound to the browser that started it. When MLflow redirects to the provider it
stores the per-login secrets — the PKCE verifier, the nonce, the redirect URI — in the session cookie.
When the browser comes back to `/callback`, those secrets must come back with it. If the cookie does
not arrive, or arrives for a different login, the exchange cannot be completed and the error is
`mismatching_state`.

Check, in this order:

1. **Start and finish on the same origin.** The browser must reach `/callback` on exactly the scheme,
   host and port it started the login on. `http://localhost:8080` and `http://127.0.0.1:8080` are
   different origins to a browser, and so are `http` and `https`. Browse MLflow at the same address
   that `OIDC_REDIRECT_URI` names, and register that same URI with the provider.
2. **Behind a reverse proxy**, either set `OIDC_REDIRECT_URI` to the public URL users browse, or
   leave it unset and set `TRUSTED_PROXIES` to the proxy's address so the callback URL is built
   from the forwarded host and scheme. Without `TRUSTED_PROXIES` the forwarded headers are ignored and
   the callback URL names the internal address. See [Reverse proxies](configuration#reverse-proxies).
3. **The cookie must be allowed back.**
   - With `SESSION_COOKIE_SECURE=true` the browser keeps the cookie only over `https`. Use it only
     when MLflow is served over `https`.
   - Keep `SESSION_COOKIE_SAMESITE=lax` (the default). The return from the provider is a cross-site
     navigation, and `strict` withholds the cookie on it.
4. **Every replica must share `SECRET_KEY`.** A cookie signed by one replica cannot be read by
   another. Without `SECRET_KEY` each process generates its own at startup and logs a warning.
5. **Each login can be completed once.** Refreshing the `/callback` page, or going back to it,
   replays an authorization code the provider has already accepted. Start the login again.

!> **Upgrade first if you run a version older than 7.14.0.** Older versions retried a failed code
exchange, and the retry always ended in `mismatching_state`. That hid the real error — for
example the provider rejecting the code, or a signing key not being found. Current versions report
the original error.

## Microsoft Entra ID (Azure AD)

A working minimal configuration:

```bash
OIDC_DISCOVERY_URL=https://login.microsoftonline.com/<tenant-id>/v2.0/.well-known/openid-configuration
OIDC_CLIENT_ID=<application (client) id>
OIDC_CLIENT_SECRET=<client secret>
OIDC_REDIRECT_URI=https://mlflow.example.com/callback
OIDC_SCOPE=openid profile email
OIDC_GROUP_NAME=<object id of the group allowed to log in>
OIDC_ADMIN_GROUP_NAME=<object id of the admin group>
```

- **Use the tenant-specific v2.0 discovery URL.** Put your tenant ID in the URL, not `common` or
  `organizations`. The multi-tenant endpoints publish an issuer template and a key set that do not
  line up with the tokens a single tenant issues, and the login fails with a key or issuer error.
- **Register the redirect URI under the "Web" platform** of the app registration, exactly as
  `OIDC_REDIRECT_URI` spells it. A "Single-page application" registration is for public clients; see
  [Public clients](configuration#public-clients) if you run without a client secret. Entra accepts
  `http://localhost` for development only.
- **Scopes** may be space- or comma-separated; both are sent to Entra space-separated (since 7.4.3).
- **Groups arrive as object IDs.** After adding the *groups* claim under *Token configuration*, Entra
  sends each group's object ID (a GUID), not its name. Either list object IDs in `OIDC_GROUP_NAME`
  and `OIDC_ADMIN_GROUP_NAME` (the local groups are then named by ID too), or use group names with the
  bundled Microsoft Graph plugin:

  ```bash
  OIDC_GROUP_DETECTION_PLUGIN=mlflow_oidc_auth.plugins.group_detection_microsoft_entra_id
  ```

  The plugin reads the signed-in user's groups from Microsoft Graph (`/me/memberOf`, all pages) and
  uses their display names. The login's access token must be a Graph token allowed to read group
  memberships — grant the app a delegated Graph permission such as `GroupMember.Read.All` (admin
  consent required) and request it in `OIDC_SCOPE`.
- **More than 200 groups.** Entra leaves the groups claim out of the ID token for users in too many
  groups and sends only a pointer to Graph. Those users fail the group check unless the Graph plugin
  above is configured.
- **Username.** The default `OIDC_USERNAME_FIELD=email,preferred_username` uses `email` when the
  account has one and falls back to the UPN in `preferred_username`. Accounts without a mailbox
  therefore log in under their UPN.
