"""SPIFFE JWT-SVID workload authentication."""

import hashlib
import json
import time
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from authlib.jose import JsonWebKey, jwt

import mlflow_oidc_auth.auth as auth_module
import mlflow_oidc_auth.middleware.auth_middleware as middleware_module
from mlflow_oidc_auth.middleware.auth_middleware import AuthMiddleware
from mlflow_oidc_auth.provider_registry import ProviderConfig, RegistryLoadResult, build_provider_registry
from mlflow_oidc_auth.routers.users import _ensure_local_tokens_allowed
from mlflow_oidc_auth.spiffe import SpiffeIdError, parse_spiffe_id


SPIFFE_ID = "spiffe://prokube.internal/ns/ml-team/sa/training-pipeline"
ISSUER = "https://spire-oidc.prokube.internal"
AUDIENCE = "mlflow-api"


@pytest.fixture
def issuer():
    key = JsonWebKey.generate_key("RSA", 2048, is_private=True)
    private = key.as_dict(is_private=True)
    public = key.as_dict(is_private=False)
    kid = public.get("kid") or key.thumbprint()
    private["kid"] = public["kid"] = kid
    public["use"] = "jwt-svid"
    return SimpleNamespace(private=private, public=public, kid=kid)


@pytest.fixture
def provider():
    return ProviderConfig(
        id="spire",
        type="spiffe",
        display_name="SPIRE workload identities",
        interactive=False,
        provisioning="jit",
        group_sync="none",
        admin_source="none",
        identity_binding="subject",
        issuer=ISSUER,
        discovery_url=f"{ISSUER}/.well-known/openid-configuration",
        audience=AUDIENCE,
        trust_domain="prokube.internal",
        spiffe_id_allowlist=(SPIFFE_ID,),
    )


@pytest.fixture
def configured(provider, issuer, monkeypatch):
    human = ProviderConfig(
        id="human",
        type="oidc",
        issuer="https://human.invalid",
        discovery_url="https://human.invalid/.well-known/openid-configuration",
        audience="mlflow-human",
    )
    monkeypatch.setattr(auth_module.config, "AUTH_PROVIDERS", RegistryLoadResult(providers=[human, provider], source="env"))
    monkeypatch.setattr(auth_module, "_get_provider_jwks", lambda selected, force_refresh=False: {"keys": [issuer.public]})

    def mint(**overrides):
        now = int(time.time())
        claims = {"iss": ISSUER, "aud": AUDIENCE, "sub": SPIFFE_ID, "iat": now, "exp": now + 300}
        for claim, value in overrides.items():
            if value is None:
                claims.pop(claim, None)
            else:
                claims[claim] = value
        return jwt.encode({"alg": "RS256", "kid": issuer.kid}, claims, issuer.private).decode()

    return mint


class TestProviderRegistration:
    @staticmethod
    def build(**overrides):
        entry = {
            "id": "spire",
            "type": "spiffe",
            "display_name": "SPIRE workload identities",
            "issuer": ISSUER,
            "discovery_url": f"{ISSUER}/.well-known/openid-configuration",
            "audience": AUDIENCE,
            "trust_domain": "prokube.internal",
            "spiffe_id_allowlist": [SPIFFE_ID],
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

    def test_a_complete_spiffe_provider_is_non_interactive_and_safe_by_default(self):
        result = self.build()

        assert result.errors == []
        assert len(result.providers) == 1
        provider = result.providers[0]
        assert provider.interactive is False
        assert provider.admin_source == "none"
        assert provider.group_sync == "none"
        assert provider.spiffe_id_allowlist == (SPIFFE_ID,)

    @pytest.mark.parametrize("missing", ["issuer", "discovery_url", "audience", "trust_domain", "spiffe_id_allowlist"])
    def test_every_security_boundary_is_required(self, missing):
        overrides = {missing: [] if missing == "spiffe_id_allowlist" else None}
        result = self.build(**overrides)

        assert result.providers == []
        assert any(missing in error for error in result.errors)

    def test_a_spiffe_provider_cannot_be_interactive(self):
        result = self.build(interactive=True)

        assert result.providers == []

    def test_a_shared_issuer_rejects_both_oidc_and_spiffe_policies(self):
        spiffe = {
            "id": "spire",
            "type": "spiffe",
            "issuer": ISSUER,
            "discovery_url": f"{ISSUER}/.well-known/openid-configuration",
            "audience": AUDIENCE,
            "trust_domain": "prokube.internal",
            "spiffe_id_allowlist": [SPIFFE_ID],
        }
        oidc = {
            "id": "human",
            "type": "oidc",
            "issuer": ISSUER,
            "discovery_url": f"{ISSUER}/.well-known/openid-configuration",
            "audience": AUDIENCE,
        }

        class Manager:
            @staticmethod
            def get(key, default=None):
                return [oidc, spiffe] if key == "AUTH_PROVIDERS" else default

        result = build_provider_registry(Manager(), SimpleNamespace())

        assert result.providers == []

    def test_an_invalid_spiffe_entry_still_disables_a_colliding_oidc_policy(self):
        human = {
            "id": "human",
            "type": "oidc",
            "issuer": ISSUER,
            "discovery_url": f"{ISSUER}/.well-known/openid-configuration",
            "audience": AUDIENCE,
        }
        invalid_spiffe = {
            "id": "spire",
            "type": "spiffe",
            "issuer": ISSUER,
            "discovery_url": f"{ISSUER}/.well-known/openid-configuration",
            "audience": AUDIENCE,
            "trust_domain": "INVALID TRUST DOMAIN",
            "spiffe_id_allowlist": [SPIFFE_ID],
        }

        class Manager:
            @staticmethod
            def get(key, default=None):
                return [human, invalid_spiffe] if key == "AUTH_PROVIDERS" else default

        result = build_provider_registry(Manager(), SimpleNamespace())

        assert result.providers == []

    @pytest.mark.parametrize("field,value", [("admin_source", "claims"), ("group_sync", "every_login"), ("identity_binding", "email")])
    def test_workload_claims_cannot_confer_human_policy(self, field, value):
        result = self.build(**{field: value})

        assert result.providers == []


class TestJwtSvidValidation:
    def test_an_allowlisted_jwt_svid_validates(self, configured):
        assert auth_module.validate_token(configured())["sub"] == SPIFFE_ID

    @pytest.mark.parametrize("claim", ["sub", "aud", "exp"])
    def test_required_claims_cannot_be_omitted(self, configured, claim):
        overrides = {claim: None}
        token = configured(**overrides)

        with pytest.raises(Exception):
            auth_module.validate_token(token)

    def test_the_wrong_audience_is_rejected(self, configured):
        with pytest.raises(Exception):
            auth_module.validate_token(configured(aud="spire-server"))

    def test_an_expired_svid_is_rejected(self, configured):
        with pytest.raises(Exception):
            auth_module.validate_token(configured(exp=int(time.time()) - 1))

    def test_an_unknown_issuer_has_no_fallback(self, configured):
        with pytest.raises(ValueError, match="does not match any configured provider"):
            auth_module.validate_token(configured(iss="https://unknown.invalid"))

    def test_a_missing_issuer_has_no_fallback(self, configured):
        with pytest.raises(ValueError, match="no issuer"):
            auth_module.validate_token(configured(iss=None))

    def test_only_jwt_svid_keys_are_applicable(self, provider, issuer, monkeypatch):
        wrong_use = dict(issuer.public, use="sig")
        monkeypatch.setattr(auth_module.config, "AUTH_PROVIDERS", RegistryLoadResult(providers=[provider], source="env"))
        monkeypatch.setattr(auth_module, "_get_provider_jwks", lambda selected, force_refresh=False: {"keys": [wrong_use]})
        now = int(time.time())
        token = jwt.encode(
            {"alg": "RS256", "kid": issuer.kid},
            {"iss": ISSUER, "aud": AUDIENCE, "sub": SPIFFE_ID, "exp": now + 300},
            issuer.private,
        ).decode()

        with pytest.raises(ValueError, match="jwt-svid"):
            auth_module.validate_token(token)

    def test_a_key_for_another_use_cannot_shadow_a_jwt_svid_key(self, configured, issuer, monkeypatch):
        foreign = JsonWebKey.generate_key("RSA", 2048, is_private=True).as_dict(is_private=False)
        foreign.update({"kid": issuer.kid, "use": "sig"})
        monkeypatch.setattr(auth_module, "_get_provider_jwks", lambda selected, force_refresh=False: {"keys": [foreign, issuer.public]})

        assert auth_module.validate_token(configured())["sub"] == SPIFFE_ID


class TestSpiffeIdPolicy:
    @pytest.mark.parametrize(
        "subject",
        [
            "SPIFFE://prokube.internal/ns/team/sa/job",
            "https://prokube.internal/ns/team/sa/job",
            "spiffe://user@prokube.internal/ns/team/sa/job",
            "spiffe://prokube.internal:443/ns/team/sa/job",
            "spiffe://prokube.internal/ns/team/sa/job?x=1",
            "spiffe://prokube.internal/ns/team/sa/job#fragment",
            "spiffe://prokube.internal/ns//sa/job",
            "spiffe://prokube.internal/ns/../sa/job",
            "spiffe://prokube.internal/ns/team/sa/job/",
        ],
    )
    def test_malformed_ids_are_rejected(self, subject):
        with pytest.raises(SpiffeIdError):
            parse_spiffe_id(subject, "prokube.internal")

    def test_path_case_is_not_normalized(self):
        lower = parse_spiffe_id("spiffe://prokube.internal/ns/team/sa/job")
        upper = parse_spiffe_id("spiffe://prokube.internal/ns/Team/sa/job")

        assert lower.spiffe_id != upper.spiffe_id
        assert lower.username != upper.username

    def test_the_username_is_the_sha256_of_the_exact_id(self):
        identity = parse_spiffe_id(SPIFFE_ID)

        assert identity.username == f"workload.{hashlib.sha256(SPIFFE_ID.encode()).hexdigest()}@spiffe.local"

    def test_ambiguous_paths_cannot_collide(self):
        first = parse_spiffe_id("spiffe://prokube.internal/ns/prod-etl/sa/writer")
        second = parse_spiffe_id("spiffe://prokube.internal/ns/prod/sa/etl-writer")

        assert first.username != second.username


class TestRequestPolicyAndProvisioning:
    def test_an_unknown_spiffe_id_is_denied_and_audited(self, provider):
        events = []
        unknown = "spiffe://prokube.internal/ns/ml-team/sa/unknown"
        middleware_module._denial_audit_seen.clear()
        with patch.object(middleware_module, "emit_audit_event", lambda event, **kwargs: events.append((event, kwargs))):
            outcome = AuthMiddleware(MagicMock())._authenticate_spiffe_workload({"sub": unknown}, provider)

        assert outcome[0] is False
        assert events[0][0] == "auth.denied_spiffe_id"
        assert events[0][1]["detail"]["spiffe_id"] == unknown

    def test_a_wrong_trust_domain_is_denied_and_audited(self, provider):
        events = []
        foreign = "spiffe://foreign.internal/ns/ml-team/sa/training-pipeline"
        middleware_module._denial_audit_seen.clear()
        with patch.object(middleware_module, "emit_audit_event", lambda event, **kwargs: events.append((event, kwargs))):
            outcome = AuthMiddleware(MagicMock())._authenticate_spiffe_workload({"sub": foreign}, provider)

        assert outcome[0] is False
        assert events[0][0] == "auth.denied_spiffe_trust_domain"

    def test_removing_an_id_revokes_an_existing_workload(self, provider):
        middleware = AuthMiddleware(MagicMock())
        assert middleware._authenticate_spiffe_workload({"sub": SPIFFE_ID}, provider)[0] is True

        revoked = replace(provider, spiffe_id_allowlist=())
        assert middleware._authenticate_spiffe_workload({"sub": SPIFFE_ID}, revoked)[0] is False

    def test_provisioning_preserves_the_external_identity_and_mints_no_local_token(self, provider):
        identity = parse_spiffe_id(SPIFFE_ID, provider.trust_domain)
        events = []
        with (
            patch.object(middleware_module, "store") as store,
            patch.object(middleware_module, "emit_audit_event", lambda event, **kwargs: events.append((event, kwargs))),
        ):
            AuthMiddleware._provision_spiffe_workload(identity, provider)

        store.provision_workload_identity.assert_called_once_with(
            username=identity.username,
            display_name=SPIFFE_ID,
            provider_id="spire",
            subject=SPIFFE_ID,
            managed_by="spiffe:spire",
        )
        assert events[0][0] == "user.provisioned"
        assert events[0][1]["detail"]["external_identity"] == SPIFFE_ID

    def test_a_workload_is_non_admin_even_if_the_database_flag_was_changed(self):
        middleware = AuthMiddleware(MagicMock())
        profile = SimpleNamespace(is_admin=True, active=True, managed_by="spiffe:spire", is_service_account=True)
        with patch.object(middleware_module, "store") as store:
            store.get_user_profile.return_value = profile
            state = middleware._get_user_auth_state("workload.example@spiffe.local", "spiffe:spire")

        assert state == (False, True, "")

    def test_a_human_username_collision_is_denied(self):
        middleware = AuthMiddleware(MagicMock())
        profile = SimpleNamespace(is_admin=True, active=True, managed_by="manual", is_service_account=False)
        with patch.object(middleware_module, "store") as store:
            store.get_user_profile.return_value = profile
            state = middleware._get_user_auth_state("workload.example@spiffe.local", "spiffe:spire")

        assert state[1] is False
        assert state[2] == middleware_module.DENIAL_IDENTITY_MISMATCH

    def test_a_local_token_cannot_bypass_spiffe_policy(self):
        middleware = AuthMiddleware(MagicMock())
        profile = SimpleNamespace(is_admin=False, active=True, managed_by="spiffe:spire", is_service_account=True)
        with patch.object(middleware_module, "store") as store:
            store.get_user_profile.return_value = profile
            state = middleware._get_user_auth_state("workload.example@spiffe.local")

        assert state == (False, False, middleware_module.DENIAL_IDENTITY_MISMATCH)

    @pytest.mark.asyncio
    async def test_a_server_side_session_cannot_bypass_spiffe_policy(self):
        middleware = AuthMiddleware(MagicMock())
        middleware._authenticate_user = AsyncMock(return_value=(True, "workload.example@spiffe.local", ""))
        request = MagicMock()
        request.url.path = "/api/protected"
        request.state.resolved_session = SimpleNamespace(is_admin=True, is_active=True, managed_by="spiffe:spire")
        call_next = AsyncMock()

        response = await middleware.dispatch(request, call_next)

        assert response.status_code == 401
        call_next.assert_not_awaited()

    def test_a_spiffe_workload_cannot_create_a_local_token(self):
        profile = SimpleNamespace(managed_by="spiffe:spire")
        with patch("mlflow_oidc_auth.routers.users.store") as store:
            store.get_user_profile.return_value = profile
            with pytest.raises(Exception) as exc_info:
                _ensure_local_tokens_allowed("workload.example@spiffe.local")

        assert getattr(exc_info.value, "status_code", None) == 403

    def test_atomic_provisioning_persists_identity_without_a_local_token(self, tmp_path):
        from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore

        store = SqlAlchemyStore()
        store.init_db(f"sqlite:///{tmp_path / 'auth.db'}")
        identity = parse_spiffe_id(SPIFFE_ID)

        user = store.provision_workload_identity(identity.username, SPIFFE_ID, "spire", SPIFFE_ID, "spiffe:spire")

        assert user.is_admin is False
        assert user.is_service_account is True
        assert user.display_name == SPIFFE_ID
        assert store.user_identity_repo.get_username_by_identity("spire", SPIFFE_ID) == identity.username
        assert store.list_user_tokens(identity.username) == []

        session_id = store.create_auth_session(identity.username, expires_at=datetime.now(timezone.utc) + timedelta(minutes=5))
        assert store.resolve_auth_session(session_id).managed_by == "spiffe:spire"
