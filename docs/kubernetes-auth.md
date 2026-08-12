# Kubernetes service accounts

Let a pod authenticate to MLflow with its projected service-account token, while human login
stays on your OIDC provider. This is the automation half of multi-provider support: these tokens
can never be provisioned by SCIM — your corporate directory does not know they exist — which is
why the policy for them is per-provider rather than global.

## What a pod presents

A projected service-account token is an ordinary JWT signed by the cluster. Its `sub` is
`system:serviceaccount:<namespace>:<name>`, and its `aud` is whatever the pod's volume
projection asked for:

```yaml
volumes:
  - name: mlflow-token
    projected:
      sources:
        - serviceAccountToken:
            path: token
            audience: mlflow-api        # must match the provider's audience
            expirationSeconds: 3600
```

The pod reads `/var/run/secrets/.../mlflow-token/token` and sends it as
`Authorization: Bearer <token>`.

The username MLflow uses comes from `sub`, not from `OIDC_USERNAME_FIELD` — a service-account
token carries no `email` or `preferred_username`, and making the global field list include `sub`
to accommodate it would change how every other provider's tokens are named.

## Configuring the provider

```json
{
  "id": "cluster",
  "type": "k8s",
  "display_name": "Kubernetes",
  "audience": "mlflow-api",
  "issuer": "https://kubernetes.default.svc",
  "namespace_allowlist": ["team-a", "team-b"],
  "jwks_uri": "https://kubernetes.default.svc/openid/v1/jwks",
  "in_cluster": true
}
```

`audience`, `issuer` and `namespace_allowlist` are all required, and the reasons are not
interchangeable:

- **`audience`** — an unpinned audience accepts any pod's token for any service. A token minted
  for another application is otherwise a valid MLflow credential.
- **`issuer`** — without it nothing checks `iss`, so any issuer whose keys you happen to trust is
  accepted.
- **`namespace_allowlist`** — this is the whole authorization decision. A service-account token
  carries **no groups claim**, so the group gate that guards OIDC bearer provisioning cannot
  apply. An empty list means *nobody*, never everybody: otherwise every pod in the cluster that
  can read its own projected token becomes an MLflow user the moment you configure the provider.

  It is checked on **every request**, not only when the user record is created — so removing a
  namespace from the list revokes access for service accounts that already authenticated, rather
  than leaving them with the row and group they were given.

## Getting the cluster's keys

The usual failure here is not validation, it is *reachability*. `system:service-account-issuer-discovery`
is not bound to `system:unauthenticated` on most clusters, and the API server is often not
reachable from wherever MLflow runs. Three modes, in order of how often they are the answer:

### 1. `jwks_uri` + `in_cluster` — MLflow runs in the cluster

```json
{"jwks_uri": "https://kubernetes.default.svc/openid/v1/jwks", "in_cluster": true}
```

The fetch authenticates with MLflow's own pod service-account token and verifies the API server
against the mounted cluster CA. Grant the reader:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: mlflow-issuer-discovery
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: system:service-account-issuer-discovery
subjects:
  - kind: ServiceAccount
    name: mlflow
    namespace: mlflow
```

### 2. `jwks_inline` — the cluster is unreachable from MLflow

Paste the key set into configuration. No network in the authentication path at all, which is the
only thing that works when MLflow runs outside the cluster and the API server is not exposed:

```bash
kubectl get --raw /openid/v1/jwks
```

```json
{"jwks_inline": "{\"keys\":[{\"kty\":\"RSA\",...}]}"}
```

The trade is that **you own key rotation**. When the cluster rotates its service-account signing
key, this value must be updated or every pod stops authenticating. Prefer mode 1 or 3 if you can
reach the cluster at all.

### 3. `discovery_url` — public discovery

For a managed cluster whose issuer is a public HTTPS endpoint (EKS, GKE and AKS all publish
one), the ordinary OIDC path works:

```json
{"discovery_url": "https://oidc.eks.eu-west-1.amazonaws.com/id/EXAMPLE/.well-known/openid-configuration"}
```

Use `ca_bundle_path` with any mode when the endpoint presents a certificate from a private CA.
It **pins** that authority rather than loosening anything: only that CA may sign, instead of
every public root.

`in_cluster` refuses to start a fetch when no CA bundle is available rather than falling back to
the global `OIDC_VERIFY_SSL`: that flag is often set false to work around a private-CA IdP, and
inheriting it here would mean fetching a cluster's signing keys, and presenting the pod's
credential, over an unverified connection.

The pod's credential is sent **only** to a `jwks_uri` you configured. It is deliberately not
attached to the discovery path, where the follow-up request goes to whatever host the discovery
document names — on managed clusters that is routinely a third-party bucket or CDN.

## What gets created

A service account that authenticates from an allowlisted namespace is provisioned as:

| | |
|---|---|
| Username | `<name>.<namespace>@serviceaccount.cluster.local` |
| Display name | `<namespace>/<name> (service account)` |
| Group | `k8s:<namespace>` |
| `is_service_account` | `true` |
| `is_admin` | **always `false`** |

Grant permissions to the `k8s:<namespace>` group and every service account in that namespace
inherits them.

Administrator rights are never conferred from a cluster token. There is no claim a cluster could
assert that should make something an MLflow administrator, and `OIDC_TRUST_BEARER_GROUP_CLAIMS`
deliberately does not reach this path — it opts into trusting a *directory's* group names, which
is a different statement from trusting a namespace.

A token from a namespace that is not on the allowlist is **refused** — the signature is valid,
but the request does not authenticate — and the refusal is recorded as `auth.denied_namespace`.

## Why not `TokenReview`

The Kubernetes `TokenReview` API answers "is this token valid?" for a cluster that publishes no
usable discovery document at all. It was evaluated and **deliberately not implemented**:

- **It puts a network call in the authentication path.** Every authenticated request would become
  a synchronous POST to the API server. The per-request auth budget this project holds itself to
  (#305) is measured in database round trips precisely because that path is the one thing every
  API call and every UI navigation pays for; adding an unbounded network hop to it is a much
  larger regression than the query it took years to avoid.
- **It moves MLflow's availability under the API server's.** JWKS validation is offline once the
  keys are cached, so a control-plane restart or an upgrade does not interrupt authentication.
  With `TokenReview` it does.
- **It needs a permanent, powerful credential.** `system:auth-delegator` lets the holder submit
  arbitrary tokens for review; JWKS needs only public keys.
- **It buys little.** Every cluster that can run `TokenReview` also has service-account issuer
  discovery available to a credential that is allowed to read it — the same credential
  `TokenReview` would require. Mode 1 covers those clusters, and `jwks_inline` covers the rest.

[opendatahub-io/mlflow-kubernetes-plugins](https://github.com/opendatahub-io/mlflow-kubernetes-plugins)
solves the same problem and is worth reading if your cluster does not fit any of the three modes
above; its approach is a separate plugin rather than a provider inside this one.

If a deployment genuinely needs `TokenReview`, open an issue describing the cluster — it belongs
behind an explicit opt-in with its own caching, not as a default path.

## Verifying against a real cluster

The automated tests mint tokens with a local key rather than a cluster, so this procedure is the
end-to-end check. It needs a cluster and cannot run in CI:

```bash
kind create cluster --name mlflow-auth
kubectl create namespace team-a
kubectl create serviceaccount trainer -n team-a
kubectl get --raw /openid/v1/jwks > /tmp/cluster-jwks.json
kubectl get --raw /.well-known/openid-configuration | jq -r .issuer     # -> provider "issuer"

# Mint a token with MLflow's audience, exactly as a projected volume would
kubectl create token trainer -n team-a --audience mlflow-api --duration 1h
```

Configure the provider with `jwks_inline` set to the contents of `/tmp/cluster-jwks.json` and
the issuer printed above, then:

```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:5000/oidc/api/whoami
```

Expect `trainer.team-a@serviceaccount.cluster.local`. Then repeat with a service account in a
namespace that is not on the allowlist and confirm no user is created.
