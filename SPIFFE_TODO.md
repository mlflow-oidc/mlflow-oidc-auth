# SPIFFE JWT-SVID TODO

Temporary checklist for `feature/spiffe-jwt-svid-v2`. Move unfinished work to a GitHub issue and
remove this file before merging.

## Required before merge

- [ ] Support valid SPIFFE IDs longer than 255 characters on PostgreSQL.
  - Decide whether to widen `users.display_name` and `user_identities.subject` or store a bounded
    display value while preserving the complete external identity.
  - Add a reversible migration when column types change.
  - Test upgrade and downgrade on SQLite and PostgreSQL.
- [ ] Add an end-to-end first-request provisioning test.
  - Send a valid JWT-SVID for a user that does not exist.
  - Verify that the request succeeds and creates a non-admin service account.
  - Verify that the external identity is bound and no local access token is created.
  - Verify that the next request stays within the two-query authentication budget.
- [ ] Add PostgreSQL provisioning coverage.
  - Cover the maximum supported SPIFFE ID length.
  - Cover concurrent first requests for the same SPIFFE ID.
  - Verify that collisions with existing human accounts fail closed.
- [ ] Run CI against the rebased branch and resolve all branch-related failures.
- [ ] Open the upstream pull request against `mlflow-oidc/mlflow-oidc-auth:main`.

## Standards and hardening

- [ ] Verify the trust-domain and path grammar against the current SPIFFE ID specification.
  - Add boundary tests for every accepted character.
  - Add negative tests for non-canonical and over-length IDs.
- [ ] Restrict SPIFFE providers to JWT-SVID signing algorithms defined by the specification.
- [ ] Validate JWT-SVID JOSE header constraints, including `typ` and unsupported private headers.
- [ ] Verify that discovery metadata `issuer` exactly matches the configured issuer.
- [ ] Add route-level tests proving that every local token-creation endpoint rejects
  SPIFFE-managed accounts, including administrator-created tokens.

## Verification

- [ ] `pre-commit run --all-files`
- [ ] `pytest mlflow_oidc_auth/tests/test_spiffe_provider.py mlflow_oidc_auth/tests/test_provider_registry.py mlflow_oidc_auth/tests/perf/test_auth_path_baseline.py`
- [ ] `pytest mlflow_oidc_auth/tests/repository/test_auth_session.py mlflow_oidc_auth/tests/routers/test_users.py mlflow_oidc_auth/tests/test_token_algorithm_pinning.py mlflow_oidc_auth/tests/test_identity_resolution.py`
- [ ] PostgreSQL migration and provisioning tests pass in CI.
- [ ] Security review reports no authentication, provisioning, session, or local-token bypass.

## Unrelated baseline

- Nine `file:` artifact-path cases in
  `mlflow_oidc_auth/tests/hooks/test_artifact_proxy_coverage.py` currently fail independently of
  the SPIFFE diff. Track and fix them separately; do not weaken or skip those security tests in
  this branch.
