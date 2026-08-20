# SPIFFE workload identities

SPIRE-attested workloads can authenticate to MLflow with JWT-SVIDs while human login continues
to use the existing interactive OIDC provider. MLflow validates JWT-SVIDs through the SPIRE OIDC
Discovery Provider; it does not contact the SPIRE Workload API itself.

## Configure SPIRE's issuer

JWT-SVIDs do not require an `iss` claim in the SPIFFE specification, but multi-provider routing
does. Configure SPIRE Server's `jwt_issuer` to the exact issuer exposed by the OIDC Discovery
Provider:

```hcl
server {
  trust_domain = "prokube.internal"
  jwt_issuer   = "https://spire-oidc.prokube.internal"
}
```

Restart or reload SPIRE Server after changing this setting. Existing JWT-SVIDs without `iss` are
rejected; obtain a new SVID after the change.

## Configure the OIDC Discovery Provider

Deploy the [SPIRE OIDC Discovery Provider](https://github.com/spiffe/oidc-discovery-provider) for
the same trust domain and publish it over HTTPS. Its discovery document must be available at:

```text
https://spire-oidc.prokube.internal/.well-known/openid-configuration
```

The discovery document's `issuer` must exactly equal `jwt_issuer`. Its `jwks_uri` must publish
the SPIRE signing keys with `use: jwt-svid`. MLflow ignores all other keys and rejects a token if
the key set contains no applicable JWT-SVID key.

## Configure MLflow

Add a non-interactive `spiffe` entry to `AUTH_PROVIDERS` alongside the human OIDC provider:

```json
[
  {
    "id": "human",
    "type": "oidc",
    "display_name": "Sign in",
    "interactive": true,
    "issuer": "https://login.example.com/realms/mlflow",
    "discovery_url": "https://login.example.com/realms/mlflow/.well-known/openid-configuration",
    "audience": "mlflow"
  },
  {
    "id": "spire",
    "type": "spiffe",
    "display_name": "SPIRE workload identities",
    "interactive": false,
    "issuer": "https://spire-oidc.prokube.internal",
    "discovery_url": "https://spire-oidc.prokube.internal/.well-known/openid-configuration",
    "audience": "mlflow-api",
    "trust_domain": "prokube.internal",
    "spiffe_id_allowlist": [
      "spiffe://prokube.internal/ns/ml-team/sa/training-pipeline",
      "spiffe://prokube.internal/ns/ml-team/sa/model-evaluator"
    ]
  }
]
```

`issuer`, `discovery_url`, `audience`, `trust_domain`, and a non-empty
`spiffe_id_allowlist` are required. Allowlist entries are exact SPIFFE IDs: prefixes, globs,
templates, and regular expressions are not supported. An empty allowlist admits nobody.

Use an audience dedicated to MLflow, such as `mlflow-api`. Do not use the trust-domain root or a
broad audience shared by unrelated services. Removing an ID from the allowlist denies it on its
next request even though its local MLflow service-account row remains.

## Obtain and use a JWT-SVID

A workload obtains a JWT-SVID for the configured MLflow audience from its local SPIRE Workload
API. With the SPIRE Agent CLI available in the workload:

```bash
JWT_SVID="$(spire-agent api fetch jwt -audience mlflow-api \
  | awk -F': ' '/^SVID:/ {print $2; exit}')"
```

The exact client command depends on the workload's SPIFFE SDK. The important requirement is that
the audience passed to the Workload API is exactly `mlflow-api`.

MLflow clients send the JWT-SVID through `MLFLOW_TRACKING_TOKEN`:

```bash
export MLFLOW_TRACKING_URI="https://mlflow.example.com"
export MLFLOW_TRACKING_TOKEN="$JWT_SVID"
mlflow experiments search
```

On first authentication, MLflow creates a non-admin service account named
`workload.<sha256-of-exact-spiffe-id>@spiffe.local`. The complete SPIFFE ID remains the display
name and persisted external identity. JWT group, role, and administrator claims are ignored.
SPIFFE-managed accounts cannot create or use local MLflow access tokens; every request must
present a currently allowlisted JWT-SVID.

## Replay risk

A JWT-SVID is a bearer credential. Anyone who obtains it can replay it until `exp`, so request
short lifetimes from SPIRE, avoid writing tokens to logs or durable files, and obtain a fresh
JWT-SVID for each short-lived pipeline or sandbox execution. Transport MLflow traffic over TLS.

This integration validates JWT-SVIDs only. X.509-SVID and mutual-TLS authentication are not part
of this feature.
