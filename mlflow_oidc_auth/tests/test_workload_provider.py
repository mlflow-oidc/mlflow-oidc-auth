"""Brokered OIDC workload authentication."""

import hashlib
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import mlflow_oidc_auth.middleware.auth_middleware as middleware_module
from mlflow_oidc_auth.middleware.auth_middleware import AuthMiddleware
from mlflow_oidc_auth.provider_registry import ProviderConfig, build_provider_registry
from mlflow_oidc_auth.routers.users import _ensure_local_tokens_allowed
from mlflow_oidc_auth.workload import WorkloadIdentityError, parse_workload_identity

ISSUER = "https://identity.example.test/auth/realms/workloads"
SUBJECT = "0b80e081-230d-44b0-aa01-9fcc9a2c6723"
CLIENT_ID = "mlflow-team-a-reader"


@pytest.fixture
def provider():
    return ProviderConfig(
        id="keycloak-workloads",
        type="workload",
        display_name="Keycloak workloads",
        interactive=False,
        provisioning="jit",
        group_sync="none",
        admin_source="none",
        identity_binding="subject",
        issuer=ISSUER,
        discovery_url=f"{ISSUER}/.well-known/openid-configuration",
        audience="mlflow-api",
        workload_client_id_claim="azp",
        workload_client_id_allowlist=(CLIENT_ID,),
    )


def _build_provider(**overrides):
    entry = {
        "id": "keycloak-workloads",
        "type": "workload",
        "issuer": ISSUER,
        "discovery_url": f"{ISSUER}/.well-known/openid-configuration",
        "audience": "mlflow-api",
        "workload_client_id_allowlist": [CLIENT_ID],
    }
    entry.update(overrides)

    class Manager:
        @staticmethod
        def get(key, default=None):
            return json.dumps([entry]) if key == "AUTH_PROVIDERS" else default

    legacy = SimpleNamespace(
        OIDC_PROVIDER_DISPLAY_NAME="OIDC",
        OIDC_AUDIENCE=None,
        OIDC_ISSUER=None,
        OIDC_DISCOVERY_URL=None,
        OIDC_CLIENT_ID=None,
    )
    return build_provider_registry(Manager(), legacy)


def test_provider_is_non_interactive_and_safe_by_default():
    result = _build_provider()

    assert result.errors == []
    loaded = result.providers[0]
    assert loaded.interactive is False
    assert loaded.provisioning == "jit"
    assert loaded.group_sync == "none"
    assert loaded.admin_source == "none"
    assert loaded.identity_binding == "subject"
    assert loaded.workload_client_id_claim == "azp"
    assert loaded.workload_client_id_allowlist == (CLIENT_ID,)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("interactive", True),
        ("provisioning", "none"),
        ("group_sync", "every_login"),
        ("admin_source", "claims"),
        ("identity_binding", "email"),
        ("workload_client_id_allowlist", []),
        ("workload_client_id_claim", "aud"),
        ("workload_client_id_claim", "sub"),
    ],
)
def test_provider_rejects_weakened_policy(field, value):
    result = _build_provider(**{field: value})

    assert result.providers == []
    assert result.errors


def test_identity_is_bound_to_issuer_and_subject():
    identity = parse_workload_identity({"sub": SUBJECT, "azp": CLIENT_ID}, ISSUER, "azp", (CLIENT_ID,))
    expected = hashlib.sha256(f"{ISSUER}\0{CLIENT_ID}\0{SUBJECT}".encode()).hexdigest()

    assert identity.username == f"workload.{expected}@oidc.local"
    assert identity.fingerprint == f"sha256:{expected}"
    assert identity.client_id == CLIENT_ID


def test_clients_with_same_subject_get_distinct_principals():
    reader = parse_workload_identity({"sub": SUBJECT, "azp": "reader"}, ISSUER, "azp", ("reader", "writer"))
    writer = parse_workload_identity({"sub": SUBJECT, "azp": "writer"}, ISSUER, "azp", ("reader", "writer"))

    assert reader.username != writer.username
    assert reader.fingerprint != writer.fingerprint


@pytest.mark.parametrize(
    "payload",
    [
        {"azp": CLIENT_ID},
        {"sub": SUBJECT},
        {"sub": SUBJECT, "azp": "unregistered-client"},
        {"sub": SUBJECT, "azp": [CLIENT_ID]},
    ],
)
def test_identity_rejects_missing_or_unregistered_claims(payload):
    with pytest.raises(WorkloadIdentityError):
        parse_workload_identity(payload, ISSUER, "azp", (CLIENT_ID,))


def test_middleware_accepts_only_allowlisted_client(provider):
    middleware = AuthMiddleware(MagicMock())

    accepted = middleware._authenticate_oidc_workload({"sub": SUBJECT, "azp": CLIENT_ID}, provider)
    denied = middleware._authenticate_oidc_workload({"sub": SUBJECT, "azp": "other-client"}, provider)

    assert accepted[0] is True
    assert accepted[1].endswith("@oidc.local")
    assert denied[0] is False


def test_provisioning_creates_non_admin_service_account(provider):
    identity = parse_workload_identity({"sub": SUBJECT, "azp": CLIENT_ID}, ISSUER, "azp", (CLIENT_ID,))
    store = MagicMock()
    with patch.object(middleware_module, "store", store):
        AuthMiddleware._provision_oidc_workload(identity, provider)

    store.provision_workload_identity.assert_called_once_with(
        username=identity.username,
        display_name=CLIENT_ID,
        provider_id=provider.id,
        subject=identity.fingerprint,
        managed_by="workload:keycloak-workloads",
    )


def test_workload_is_non_admin_even_if_database_flag_changes():
    profile = SimpleNamespace(
        is_admin=True,
        active=True,
        managed_by="workload:keycloak-workloads",
        is_service_account=True,
    )
    store = MagicMock()
    store.get_user_profile.return_value = profile
    with patch.object(middleware_module, "store", store):
        state = AuthMiddleware(MagicMock())._get_user_auth_state("workload.example@oidc.local", "workload:keycloak-workloads")

    assert state == (False, True, "")


def test_workload_cannot_create_a_local_token():
    store = MagicMock()
    store.get_user_profile.return_value = SimpleNamespace(managed_by="workload:keycloak-workloads")
    with patch("mlflow_oidc_auth.routers.users.store", store):
        with pytest.raises(Exception) as exc_info:
            _ensure_local_tokens_allowed("workload.example@oidc.local")

    assert getattr(exc_info.value, "status_code", None) == 403
