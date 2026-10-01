# Brokered workload authentication

The `workload` provider accepts short-lived OIDC access tokens issued to non-interactive
workloads. It is intended for brokers such as Keycloak that first authenticate a platform-native
workload credential and then issue an access token specifically for MLflow.

```json
{
  "id": "keycloak-workloads",
  "type": "workload",
  "display_name": "Keycloak workloads",
  "issuer": "https://identity.example.com/realms/workloads",
  "discovery_url": "https://identity.example.com/realms/workloads/.well-known/openid-configuration",
  "audience": "mlflow-api",
  "workload_client_id_claim": "azp",
  "workload_client_id_allowlist": [
    "mlflow-team-a-reader",
    "mlflow-team-a-writer"
  ]
}
```

The provider is always non-interactive and enforces these policies:

- `provisioning` is `jit`.
- `group_sync` is `none`.
- `admin_source` is `none`.
- `identity_binding` is `subject`.
- The configured audience, issuer, signature, expiry, subject, and exact client allowlist must all
  validate.

An accepted `(issuer, client ID, sub)` tuple is provisioned as a non-admin MLflow service account.
The tuple is stored only as a SHA-256 fingerprint, while the client ID becomes the display name.
`workload_client_id_claim` is restricted to `azp` or `client_id`; registered claims such as `aud`,
`iss`, and `sub` cannot accidentally replace the client boundary.

Workload-managed accounts cannot authenticate through an MLflow session or local access token.
Removing a client from `workload_client_id_allowlist` stops new bearer authentication immediately;
the inactive database row may remain for audit and permission cleanup.

## Keycloak with SPIFFE

A SPIFFE-backed Keycloak client can use its JWT-SVID as a federated client assertion:

```text
grant_type=client_credentials
client_id=mlflow-team-a-reader
client_assertion_type=urn:ietf:params:oauth:client-assertion-type:jwt-spiffe
client_assertion=<JWT-SVID>
```

The resulting Keycloak access token, not the JWT-SVID, is sent to MLflow. Configure Keycloak to:

- bind each client to one exact SPIFFE ID;
- issue the dedicated MLflow audience;
- include a non-empty `sub` and the allowlisted client identifier in `azp`;
- omit MLflow administrator and group-derived permissions.

MLflow permissions remain authoritative. Grant each provisioned service account only its intended
workspace and resource permissions, and keep `DEFAULT_MLFLOW_PERMISSION=NO_PERMISSIONS`.
