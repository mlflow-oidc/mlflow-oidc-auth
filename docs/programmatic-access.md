# Programmatic access

Anything that is not a browser — the MLflow Python client, the CLI, `curl`, a CI job, a pod —
authenticates with one of two credentials:

- a **bearer token** issued by an identity provider or a Kubernetes cluster, sent as
  `Authorization: Bearer <token>`, or
- a **personal access token** issued by this plugin, sent as the password of HTTP basic auth.

They are not interchangeable. Workload identities are the mechanism for automation; access tokens
are for people.

| Use case | Recommended credential | Why |
|----------|------------------------|-----|
| A pod in Kubernetes (training job, batch scoring, a service) | [Kubernetes service-account token](#kubernetes-service-account-tokens) | Projected, audience-bound and rotated by the kubelet; nothing to store |
| A CI/CD pipeline, a scheduled job, a service outside Kubernetes | [IdP client-credentials or workload-identity token](#idp-client-credentials-and-workload-identity) | Short-lived, issued and revocable at the IdP, rotated by the platform |
| A person running the MLflow client from a laptop or notebook | [Personal access token](#interactive-and-research-work-personal-access-tokens) | Works with `MLFLOW_TRACKING_USERNAME` / `MLFLOW_TRACKING_PASSWORD`; created and deleted by that person |
| A tool that can only send basic auth and cannot obtain a bearer token | [Admin-issued token for a service account](#when-an-admin-issued-token-for-a-service-account-is-acceptable) | The exception: a long-lived secret someone has to store and rotate |

## Automation: OIDC service accounts

**A service account signs in one way.** It is either **internal** — it signs in only with access
tokens issued for it (basic auth), and no identity provider's token reaches it, whatever username
the token claims — or **external** to one provider, whose tokens alone reach it, for the subject
bound to it. A new service account is internal unless an administrator chooses a provider; a
Kubernetes service account is its cluster provider's. No service account signs in through the
browser.

A workload identity is short-lived, rotated by the platform that issues it, revocable at the
source (the IdP or the cluster), and nothing long-lived has to be stored in the pipeline. Tokens
from a Kubernetes provider or from a provider configured `interactive: false` cannot be turned
into a longer-lived credential: they get `403` from every endpoint that issues an access token.
A client-credentials token from the IdP people sign in with is treated like any IdP token and
may issue access tokens for its own account (see [Security notes](#security-notes)).

### Kubernetes service-account tokens

A pod presents its projected service-account token and the plugin validates it natively — no
TokenReview call, no IdP round trip. Configuration, the namespace allowlist, and what account and
group each service account is given are in [Kubernetes service accounts](kubernetes-auth).

The MLflow Python client sends `MLFLOW_TRACKING_TOKEN` as `Authorization: Bearer <token>`. Point
it at the projected token:

```yaml
spec:
  serviceAccountName: trainer
  containers:
    - name: train
      image: my-training-image
      env:
        - name: MLFLOW_TRACKING_URI
          value: https://mlflow.example.com
      command: ["sh", "-c", "MLFLOW_TRACKING_TOKEN=$(cat /var/run/secrets/mlflow/token) exec python train.py"]
      volumeMounts:
        - name: mlflow-token
          mountPath: /var/run/secrets/mlflow
          readOnly: true
  volumes:
    - name: mlflow-token
      projected:
        sources:
          - serviceAccountToken:
              path: token
              audience: mlflow-api        # must match the provider's audience
              expirationSeconds: 3600
```

The kubelet renews the file before it expires, but an environment variable read once at startup
does not follow it. For a process that runs longer than `expirationSeconds`, re-read the file:
the client resolves its credentials on every request, so updating the variable in-process is
enough.

```python
import os

TOKEN_PATH = "/var/run/secrets/mlflow/token"


def refresh_mlflow_token() -> None:
    with open(TOKEN_PATH) as f:
        os.environ["MLFLOW_TRACKING_TOKEN"] = f.read().strip()
```

Grant permissions to the `k8s:<namespace>` group (or to the individual
`<name>.<namespace>@serviceaccount.cluster.local` account) as described in
[What gets created](kubernetes-auth#what-gets-created).

### IdP client credentials and workload identity

A service principal in your IdP (a Keycloak client with service accounts enabled, an Entra app
registration, an Okta service app) or a CI platform's workload-identity issuer can obtain a
short-lived token and send it as a bearer token. For such a token to authenticate:

1. **A provider must accept its issuer and audience.** The token is validated by the provider
   whose `issuer` matches its `iss` (with a single provider, by that provider): signature,
   `exp`, `iss` and `aud` are all checked. For the flat `default` provider set `OIDC_AUDIENCE` and
   `OIDC_ISSUER` (see [OIDC Authentication](configuration#oidc-authentication)); a registry entry
   always requires `audience`, `issuer` and `discovery_url`. Configure the IdP to put your MLflow
   audience into the token's `aud` — many issue client-credentials tokens for a different
   audience by default.
2. **The token must carry a username claim.** The username is read from the first non-empty claim
   in `OIDC_USERNAME_FIELD` (default `email,preferred_username`), lowercased. That list is
   deployment-wide. Client-credentials tokens often carry no `email`; if yours carries none of
   the listed claims, append one it does carry — a claim at the end of the list is only used for
   tokens that have none of the earlier ones.
3. **An active account with that username must exist** (usernames are case-insensitive). A bearer token whose username has no
   account is refused. Either:
   - **create it ahead of time** — an admin creates an **external** service account with exactly
     that username, bound to the provider that issues the token: on the **Service Accounts** page
     choose that provider as its sign-in source, or `POST /api/2.0/mlflow/users` with
     `"is_service_account": true` and `"service_account_source": "<provider-id>"`
     ([API reference](api-reference#user-management)), then grant it permissions. Give the
     token's subject (`"subject": "<sub>"`) to bind it now — for example
     `repo:org/app:ref:refs/heads/main` for a GitHub Actions workflow — or leave it out and the
     first token from that provider binds its subject (an administrator service account must be
     given its subject: no first token binds one). Only that provider's tokens, for that
     subject, reach the account, and no access token can be issued for it: its lifecycle lives in
     the IdP. This is the usual answer for a service principal, whose token rarely carries a
     groups claim; or
   - **let the first request create it** with `OIDC_PROVISION_ON_BEARER_AUTH=true`. The account
     is bound to the token's `(provider, sub)`, so derive the username from a stable subject; with
     several providers, a provider other than `default` writes its groups as `<provider-id>:<group>`
     and grants must name them that way. The account is created only when the validating provider pins both audience and issuer and the token's
     own groups claim (`OIDC_GROUPS_ATTRIBUTE`, or `OIDC_GROUP_DETECTION_PLUGIN`) passes the same
     `OIDC_GROUP_NAME` / `OIDC_GROUP_NAME_PATTERN` / `OIDC_ADMIN_GROUP_NAME` gate as a browser login
     from that provider, and only for a provider with `provisioning: jit`. Its groups are written as
     that login would write them, namespaced for any provider but `default`. It is never an admin
     unless `OIDC_TRUST_BEARER_GROUP_CLAIMS` is set. See the
     [configuration reference](configuration#oidc-authentication).
4. **Interactive or not is set per issuer.** A client-credentials token from the IdP people sign
   in with may issue access tokens for its own account — that is intended. A token-only issuer
   (a CI platform's OIDC issuer, a dedicated realm or tenant for workloads) is registered with
   `"interactive": false`: it is kept off the login page, and its tokens cannot issue access
   tokens:

   ```json
   {
     "id": "ci",
     "type": "oidc",
     "display_name": "CI workloads",
     "interactive": false,
     "discovery_url": "https://ci-issuer.example.com/.well-known/openid-configuration",
     "issuer": "https://ci-issuer.example.com",
     "audience": "mlflow-api"
   }
   ```

   The fields of a registry entry are in [Provider registry fields](configuration#provider-registry-fields).

A job then fetches a token and hands it to the MLflow client. With a client-credentials grant:

```bash
MLFLOW_TRACKING_TOKEN=$(curl -s https://idp.example.com/oauth2/token \
  -d grant_type=client_credentials \
  -d client_id="$CLIENT_ID" -d client_secret="$CLIENT_SECRET" \
  -d scope=mlflow-api | jq -r .access_token)
export MLFLOW_TRACKING_TOKEN MLFLOW_TRACKING_URI=https://mlflow.example.com
python train.py
```

The exact token endpoint and the parameter that selects the audience (`scope`, `resource` or
`audience`) depend on the IdP. A client secret is itself a stored credential, but it lives at the
IdP, is revoked there, and never reaches MLflow; where the platform offers federated workload
identity (the CI runner or cloud workload presents its own signed token instead of a secret),
prefer it.

Two things to know about the MLflow client:

- If `MLFLOW_TRACKING_USERNAME` and `MLFLOW_TRACKING_PASSWORD` are both set, the client sends
  basic auth and ignores `MLFLOW_TRACKING_TOKEN`. Unset them in a job that uses a bearer token.
- A bearer token that expires mid-run fails the next request with `401`. Fetch a fresh one (and
  update `MLFLOW_TRACKING_TOKEN`) for runs longer than the token's lifetime.

## Interactive and research work: personal access tokens

A personal access token is how a **person** uses the MLflow client outside the browser: a laptop,
a notebook, a quick experiment, an exploratory script. It acts as that person, with their
permissions.

**Create one** from the **Tokens** tab of your **User Profile** page (`/user`) — see
[Access token tabs](admin-ui#access-token-tabs) — or with `POST /api/2.0/mlflow/users/current/tokens`
from a signed-in session or your own IdP bearer token ([API reference](api-reference#access-tokens)).
The plaintext is shown **once**; copy it then.

**Use it** as the basic-auth password:

```bash
export MLFLOW_TRACKING_URI=https://mlflow.example.com
export MLFLOW_TRACKING_USERNAME=alice@example.com
export MLFLOW_TRACKING_PASSWORD=mlf_3f9a0c1b_<secret>
```

Good practice:

- **One token per device or purpose**, named for it (`laptop`, `notebook-server`,
  `churn-experiment`). Names are unique per user; the listing shows each token's name, prefix,
  expiry and last use, so a token you no longer recognise stands out.
- **Short expiry.** Every token must expire, at most one year (366 days) after creation. Pick the
  length of the work, not the maximum.
- **Rotate by replacement:** create a new token, switch to it, delete the old one. `PATCH
  /api/2.0/mlflow/users/access-token` does the same for a single token named `default`.
- **Delete it when you are done**, and immediately if it may have leaked. Deleting works with any
  credential, including the token itself.
- A user holds at most **20** unexpired tokens.

Access tokens are **not** the recommended mechanism for CI/CD, scheduled jobs or services. A
token pasted into a pipeline is a year-long secret tied to one person: it breaks when they leave
or are deactivated, and it acts with everything they are allowed to do.

## When an admin-issued token for a service account is acceptable

An admin can issue a named token for a service account (the **Tokens** tab on the service
account's page, or `POST /api/2.0/mlflow/users/{username}/tokens`). Use it only when the client
can send nothing but a username and password — a third-party tool with a basic-auth field and no
way to obtain a bearer token — and neither option above is available to it.

Accept the caveats that come with it:

- **It is a long-lived secret you have to store** in the tool's configuration or a secret manager,
  and protect like any other password.
- **Rotation is manual and cannot be automated by the tool.** Every endpoint that issues a token,
  including `PATCH /access-token`, requires an interactive sign-in, so a request authenticated
  with the token itself gets `403`. An admin creates the replacement from a signed-in session,
  the tool is reconfigured, and the old token is deleted — at least once a year, because no token
  outlives 366 days.
- **Scope it by the account, not the token.** A token carries no scope of its own; it acts with
  every permission of its service account. Give the tool its own service account with only the
  grants it needs.

## Security notes

- **Who can mint tokens.** Your own tokens: you, from a signed-in session or a bearer token from
  an interactive IdP — including that IdP's client-credentials tokens, for their own account.
  Another user's or a service account's: an admin, from the same kinds of sign-in.
- **Credentials that cannot mint.** A request authenticated with a personal access token, or
  with a bearer token from a non-interactive account (a Kubernetes service account, a provider
  configured `interactive: false`), gets `403` from every issuing endpoint. A leaked or
  short-lived credential cannot produce a year-long replacement for itself. Listing and deleting
  tokens works with any credential.
- **Only a hash is stored.** The plaintext is returned once, in the response that creates the
  token, and never again — not in a listing, not in an audit event.
- **Deactivation deletes tokens.** Deactivating an account — from the admin UI, or by SCIM for a
  directory user — revokes its sessions and deletes all of its access tokens; reactivating does
  not bring them back. Deleting the account deletes its tokens too. An admin can also
  **Revoke all tokens** of an account without deactivating it.
- **Audited.** `user.token_create`, `user.token_rotate`, `user.token_delete` and
  `user.tokens_revoked` are recorded with the token's id, prefix and name — see
  [Access tokens](api-reference#access-tokens).
- **Workload identities are revoked at the source.** Disable the service principal at the IdP
  and it gets no new tokens; the ones already issued run out at their `exp`. Remove a namespace
  from `namespace_allowlist` and its service accounts are refused once MLflow runs with the new
  configuration. To cut off a workload immediately, deactivate its MLflow account: the account
  is checked on every request, whatever the token says.
