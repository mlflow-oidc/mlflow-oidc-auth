"""Layer 2 of the #262 fix: opt-in, hardened auto-provisioning on bearer authentication."""

import importlib
import sys
import types
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from mlflow_oidc_auth.config import config as real_config
from mlflow_oidc_auth.middleware.auth_middleware import AuthMiddleware
from mlflow_oidc_auth.utils.group_detection import _accepts_token_response


@pytest.fixture(autouse=True)
def provider_carries_the_configured_scoping(monkeypatch):
    """Resolve the token's provider from whatever scoping the test configured.

    Since #313 the provisioning gate asks the provider that validated the token whether it pins
    an audience and an issuer, rather than reading the flat variables — those no longer describe
    what was enforced. These tests describe a single-provider deployment, where the synthesised
    provider carries exactly those flat values, so resolution mirrors them and every case keeps
    meaning what it did.
    """
    import mlflow_oidc_auth.auth as auth_module

    middleware_module = importlib.import_module("mlflow_oidc_auth.middleware.auth_middleware")

    def resolve(token):
        cfg = middleware_module.config
        # ``type`` matters since #314: a k8s provider takes the service-account path instead of
        # the group gate these cases describe.
        # ``admin_source`` matters since #318: a provider that may not assert administrator
        # status cannot mint one through this path either. These cases describe the deployment's
        # own provider, which may.
        return _provider(id="default", audience=cfg.OIDC_AUDIENCE, issuer=cfg.OIDC_ISSUER)

    monkeypatch.setattr(auth_module, "resolve_token_provider", resolve)


def _provider(**over):
    """A registry entry with the registry's defaults (provider_registry.ProviderConfig)."""
    fields = dict(
        id="default",
        type="oidc",
        admin_source="claims",
        audience="mlflow",
        issuer="https://idp.example.com",
        provisioning="jit",
        group_sync="every_login",
        group_sync_mode="authoritative",
    )
    fields.update(over)
    return SimpleNamespace(**fields)


def _mw():
    return AuthMiddleware(app=MagicMock())


def _cfg(mock_config, **over):
    """Sensible defaults for a fully-hardened, provisioning-enabled config."""
    mock_config.OIDC_PROVISION_ON_BEARER_AUTH = True
    mock_config.OIDC_AUDIENCE = "mlflow"
    mock_config.OIDC_ISSUER = "https://idp.example.com"
    mock_config.OIDC_GROUP_DETECTION_PLUGIN = None
    mock_config.OIDC_GROUPS_ATTRIBUTE = "groups"
    mock_config.OIDC_GROUP_NAME = ["mlflow-users"]
    mock_config.OIDC_GROUP_NAME_PATTERN = []
    mock_config.OIDC_ADMIN_GROUP_NAME = ["mlflow-admins"]
    mock_config.OIDC_TRUST_BEARER_GROUP_CLAIMS = False
    for k, v in over.items():
        setattr(mock_config, k, v)
    return mock_config


class TestProvisioningDisabled:
    def test_flag_off_does_nothing(self):
        with (
            patch("mlflow_oidc_auth.middleware.auth_middleware.config") as cfg,
            patch("mlflow_oidc_auth.middleware.auth_middleware.store") as store,
            patch("mlflow_oidc_auth.user.create_user") as create_user,
        ):
            cfg.OIDC_PROVISION_ON_BEARER_AUTH = False
            _mw()._maybe_provision_bearer_user("a@x.com", "tok", {"groups": ["mlflow-users"]})
            store.has_user.assert_not_called()
            create_user.assert_not_called()

    def test_existing_user_not_reprovisioned(self):
        with (
            patch("mlflow_oidc_auth.middleware.auth_middleware.config") as cfg,
            patch("mlflow_oidc_auth.middleware.auth_middleware.store") as store,
            patch("mlflow_oidc_auth.user.create_user") as create_user,
        ):
            _cfg(cfg)
            store.has_user.return_value = True
            _mw()._maybe_provision_bearer_user("a@x.com", "tok", {"groups": ["mlflow-users"]})
            create_user.assert_not_called()


class TestHardening:
    @pytest.mark.parametrize("aud,iss", [(None, "iss"), ("aud", None), (None, None)])
    def test_refuses_without_both_aud_and_iss(self, aud, iss):
        with (
            patch("mlflow_oidc_auth.middleware.auth_middleware.config") as cfg,
            patch("mlflow_oidc_auth.middleware.auth_middleware.store") as store,
            patch("mlflow_oidc_auth.user.create_user") as create_user,
        ):
            _cfg(cfg, OIDC_AUDIENCE=aud, OIDC_ISSUER=iss)
            store.has_user.return_value = False
            _mw()._maybe_provision_bearer_user("a@x.com", "tok", {"groups": ["mlflow-users"]})
            create_user.assert_not_called()


class TestAuthorizationGate:
    def test_user_in_no_authorized_group_not_provisioned(self):
        with (
            patch("mlflow_oidc_auth.middleware.auth_middleware.config") as cfg,
            patch("mlflow_oidc_auth.middleware.auth_middleware.store") as store,
            patch("mlflow_oidc_auth.user.create_user") as create_user,
        ):
            _cfg(cfg)
            store.has_user.return_value = False
            _mw()._maybe_provision_bearer_user("a@x.com", "tok", {"groups": ["some-other-group"]})
            create_user.assert_not_called()

    @pytest.mark.parametrize("groups", [None, [""]])
    def test_missing_or_empty_groups_fail_closed(self, groups):
        with (
            patch("mlflow_oidc_auth.middleware.auth_middleware.config") as cfg,
            patch("mlflow_oidc_auth.middleware.auth_middleware.store") as store,
            patch("mlflow_oidc_auth.user.create_user") as create_user,
        ):
            _cfg(cfg, OIDC_GROUP_NAME_PATTERN=["*"])
            store.has_user.return_value = False

            _mw()._maybe_provision_bearer_user("a@x.com", "tok", {"groups": groups})

            create_user.assert_not_called()

    def test_allowed_group_member_provisioned_non_admin(self):
        with (
            patch("mlflow_oidc_auth.middleware.auth_middleware.config") as cfg,
            patch("mlflow_oidc_auth.middleware.auth_middleware.store") as store,
            patch("mlflow_oidc_auth.user.create_user") as create_user,
            patch("mlflow_oidc_auth.user.populate_groups") as populate_groups,
            patch("mlflow_oidc_auth.user.update_user") as update_user,
        ):
            _cfg(cfg)
            store.has_user.return_value = False
            _mw()._maybe_provision_bearer_user("a@x.com", "tok", {"groups": ["mlflow-users"], "name": "Alice"})
            create_user.assert_called_once_with(username="a@x.com", display_name="Alice", is_admin=False, written_by="oidc:default")
            populate_groups.assert_called_once_with(group_names=["mlflow-users"], written_by="oidc:default")
            update_user.assert_called_once_with(username="a@x.com", group_names=["mlflow-users"], written_by="oidc:default")


class TestGroupDetectionPlugin:
    """#250: the bearer path calls ``OIDC_GROUP_DETECTION_PLUGIN`` with the token and, when the
    plugin declares it, a ``token_response`` dict carrying the token plus the validated claims.
    """

    @pytest.fixture(autouse=True)
    def _clear_signature_cache(self):
        _accepts_token_response.cache_clear()
        yield
        _accepts_token_response.cache_clear()

    def _install_plugin(self, monkeypatch, name, get_user_groups):
        module = types.ModuleType(name)
        module.get_user_groups = get_user_groups
        monkeypatch.setitem(sys.modules, name, module)

    def test_old_single_argument_plugin_still_works(self, monkeypatch):
        calls = []

        def get_user_groups(access_token):
            calls.append(access_token)
            return ["mlflow-users"]

        self._install_plugin(monkeypatch, "_test_bearer_plugin_old_sig", get_user_groups)

        with (
            patch("mlflow_oidc_auth.middleware.auth_middleware.config") as cfg,
            patch("mlflow_oidc_auth.middleware.auth_middleware.store") as store,
            patch("mlflow_oidc_auth.user.create_user") as create_user,
            patch("mlflow_oidc_auth.user.populate_groups"),
            patch("mlflow_oidc_auth.user.update_user"),
        ):
            _cfg(cfg, OIDC_GROUP_DETECTION_PLUGIN="_test_bearer_plugin_old_sig")
            store.has_user.return_value = False
            _mw()._maybe_provision_bearer_user("a@x.com", "tok-old", {"name": "Alice"})
            create_user.assert_called_once_with(username="a@x.com", display_name="Alice", is_admin=False, written_by="oidc:default")

        assert calls == ["tok-old"]

    def test_plugin_declaring_token_response_receives_token_and_claims(self, monkeypatch):
        received = {}

        def get_user_groups(access_token, token_response=None):
            received["access_token"] = access_token
            received["token_response"] = token_response
            return ["mlflow-users"]

        self._install_plugin(monkeypatch, "_test_bearer_plugin_token_response", get_user_groups)

        payload = {"name": "Alice", "sub": "alice-sub"}
        with (
            patch("mlflow_oidc_auth.middleware.auth_middleware.config") as cfg,
            patch("mlflow_oidc_auth.middleware.auth_middleware.store") as store,
            patch("mlflow_oidc_auth.user.create_user") as create_user,
            patch("mlflow_oidc_auth.user.populate_groups"),
            patch("mlflow_oidc_auth.user.update_user"),
        ):
            _cfg(cfg, OIDC_GROUP_DETECTION_PLUGIN="_test_bearer_plugin_token_response")
            store.has_user.return_value = False
            _mw()._maybe_provision_bearer_user("a@x.com", "tok-new", payload)
            create_user.assert_called_once_with(username="a@x.com", display_name="Alice", is_admin=False, written_by="oidc:default")

        assert received["access_token"] == "tok-new"
        assert received["token_response"] == {"access_token": "tok-new", "claims": payload}

    def test_group_pattern_member_is_provisioned(self):
        with (
            patch("mlflow_oidc_auth.middleware.auth_middleware.config") as cfg,
            patch("mlflow_oidc_auth.middleware.auth_middleware.store") as store,
            patch("mlflow_oidc_auth.user.create_user") as create_user,
            patch("mlflow_oidc_auth.user.populate_groups") as populate_groups,
            patch("mlflow_oidc_auth.user.update_user") as update_user,
            patch("mlflow_oidc_auth.middleware.auth_middleware.emit_audit_event") as audit_event,
        ):
            _cfg(cfg, OIDC_GROUP_NAME_PATTERN=["mlflow-*"])
            store.has_user.return_value = False
            groups = ["mlflow-new-team", "shared-data-platform"]

            _mw()._maybe_provision_bearer_user("a@x.com", "tok", {"groups": groups, "name": "Alice"})

            create_user.assert_called_once_with(username="a@x.com", display_name="Alice", is_admin=False, written_by="oidc:default")
            assert populate_groups.call_args.kwargs["group_names"] == groups
            assert update_user.call_args.kwargs["group_names"] == groups
            (call,) = [c for c in audit_event.call_args_list if c.args[0] == "auth.admitted_by_group_pattern"]
            assert call.kwargs["detail"]["pattern"] == "mlflow-*" and call.kwargs["detail"]["method"] == "bearer"


class TestAdminElevation:
    def test_admin_group_but_trust_off_stays_non_admin(self):
        """The scary case: an admin-group claim must NOT confer admin unless trust is enabled."""
        with (
            patch("mlflow_oidc_auth.middleware.auth_middleware.config") as cfg,
            patch("mlflow_oidc_auth.middleware.auth_middleware.store") as store,
            patch("mlflow_oidc_auth.user.create_user") as create_user,
            patch("mlflow_oidc_auth.user.populate_groups"),
            patch("mlflow_oidc_auth.user.update_user"),
        ):
            _cfg(cfg, OIDC_TRUST_BEARER_GROUP_CLAIMS=False)
            store.has_user.return_value = False
            _mw()._maybe_provision_bearer_user("a@x.com", "tok", {"groups": ["mlflow-admins"]})
            create_user.assert_called_once_with(username="a@x.com", display_name="a@x.com", is_admin=False, written_by="oidc:default")

    def test_admin_group_with_trust_on_confers_admin(self):
        with (
            patch("mlflow_oidc_auth.middleware.auth_middleware.config") as cfg,
            patch("mlflow_oidc_auth.middleware.auth_middleware.store") as store,
            patch("mlflow_oidc_auth.user.create_user") as create_user,
            patch("mlflow_oidc_auth.user.populate_groups"),
            patch("mlflow_oidc_auth.user.update_user"),
        ):
            _cfg(cfg, OIDC_TRUST_BEARER_GROUP_CLAIMS=True)
            store.has_user.return_value = False
            _mw()._maybe_provision_bearer_user("a@x.com", "tok", {"groups": ["mlflow-admins"]})
            create_user.assert_called_once_with(username="a@x.com", display_name="a@x.com", is_admin=True, written_by="oidc:default")


class TestConfigurableDisplayName:
    """Bearer-token provisioning must honor OIDC_DISPLAY_NAME_FIELD, not a hardcoded 'name' claim."""

    def test_provisioning_honors_configured_display_name_field(self, monkeypatch):
        """OIDC_DISPLAY_NAME_FIELD must be respected on bearer provisioning, not just interactive login."""
        monkeypatch.setattr(real_config, "OIDC_DISPLAY_NAME_FIELD", ["full_name"])
        with (
            patch("mlflow_oidc_auth.middleware.auth_middleware.config") as cfg,
            patch("mlflow_oidc_auth.middleware.auth_middleware.store") as store,
            patch("mlflow_oidc_auth.user.create_user") as create_user,
            patch("mlflow_oidc_auth.user.populate_groups"),
            patch("mlflow_oidc_auth.user.update_user"),
        ):
            _cfg(cfg)
            store.has_user.return_value = False
            _mw()._maybe_provision_bearer_user("a@x.com", "tok", {"groups": ["mlflow-users"], "name": "Alice", "full_name": "Alice Anderson"})
            create_user.assert_called_once_with(username="a@x.com", display_name="Alice Anderson", is_admin=False, written_by="oidc:default")

    def test_provisioning_falls_back_to_username_when_configured_field_missing(self, monkeypatch):
        """A present-but-unconfigured field (e.g. 'name') must not be used as a fallback source."""
        monkeypatch.setattr(real_config, "OIDC_DISPLAY_NAME_FIELD", ["full_name"])
        with (
            patch("mlflow_oidc_auth.middleware.auth_middleware.config") as cfg,
            patch("mlflow_oidc_auth.middleware.auth_middleware.store") as store,
            patch("mlflow_oidc_auth.user.create_user") as create_user,
            patch("mlflow_oidc_auth.user.populate_groups"),
            patch("mlflow_oidc_auth.user.update_user"),
        ):
            _cfg(cfg)
            store.has_user.return_value = False
            # "name" is present but not the configured field, so it must not be used.
            _mw()._maybe_provision_bearer_user("a@x.com", "tok", {"groups": ["mlflow-users"], "name": "Alice"})
            create_user.assert_called_once_with(username="a@x.com", display_name="a@x.com", is_admin=False, written_by="oidc:default")


class TestRobustness:
    def test_string_group_claim_normalized(self):
        with (
            patch("mlflow_oidc_auth.middleware.auth_middleware.config") as cfg,
            patch("mlflow_oidc_auth.middleware.auth_middleware.store") as store,
            patch("mlflow_oidc_auth.user.create_user"),
            patch("mlflow_oidc_auth.user.populate_groups") as populate_groups,
            patch("mlflow_oidc_auth.user.update_user"),
        ):
            _cfg(cfg)
            store.has_user.return_value = False
            _mw()._maybe_provision_bearer_user("a@x.com", "tok", {"groups": "mlflow-users"})
            populate_groups.assert_called_once_with(group_names=["mlflow-users"], written_by="oidc:default")

    def test_provisioning_error_is_swallowed(self):
        """A concurrent-insert IntegrityError (or any provisioning failure) must not raise."""
        with (
            patch("mlflow_oidc_auth.middleware.auth_middleware.config") as cfg,
            patch("mlflow_oidc_auth.middleware.auth_middleware.store") as store,
            patch("mlflow_oidc_auth.user.create_user", side_effect=Exception("unique constraint")),
            patch("mlflow_oidc_auth.user.populate_groups"),
            patch("mlflow_oidc_auth.user.update_user"),
        ):
            _cfg(cfg)
            store.has_user.return_value = False
            # must not raise
            _mw()._maybe_provision_bearer_user("a@x.com", "tok", {"groups": ["mlflow-users"]})


class TestTheProviderMustBeAllowedToConferAdmin:
    """#318: ``OIDC_TRUST_BEARER_GROUP_CLAIMS`` says the operator trusts group claims; the
    provider's ``admin_source`` says whether *this* provider's claims may say "administrator"."""

    def test_a_provider_with_no_admin_source_cannot_mint_an_admin(self, monkeypatch):
        import mlflow_oidc_auth.auth as auth_module

        monkeypatch.setattr(
            auth_module,
            "resolve_token_provider",
            lambda token: _provider(id="partner", admin_source="none", issuer="https://partner.invalid"),
        )

        with (
            patch("mlflow_oidc_auth.middleware.auth_middleware.config") as cfg,
            patch("mlflow_oidc_auth.middleware.auth_middleware.store") as store,
            patch("mlflow_oidc_auth.user.create_user") as create_user,
            patch("mlflow_oidc_auth.user.populate_groups"),
            patch("mlflow_oidc_auth.user.update_user"),
        ):
            _cfg(cfg, OIDC_TRUST_BEARER_GROUP_CLAIMS=True)
            store.has_user.return_value = False
            _mw()._maybe_provision_bearer_user("a@x.com", "tok", {"groups": ["mlflow-admins", "mlflow-users"]})

        assert create_user.call_args.kwargs["is_admin"] is False

    def test_an_admin_group_name_alone_does_not_admit_through_such_a_provider(self, monkeypatch):
        """Login refuses this token (the admin group name is not this provider's to assert, and it
        is in no allowed group); provisioning from it must refuse too."""
        import mlflow_oidc_auth.auth as auth_module

        monkeypatch.setattr(auth_module, "resolve_token_provider", lambda token: _provider(id="partner", admin_source="none"))

        with (
            patch("mlflow_oidc_auth.middleware.auth_middleware.config") as cfg,
            patch("mlflow_oidc_auth.middleware.auth_middleware.store") as store,
            patch("mlflow_oidc_auth.user.create_user") as create_user,
        ):
            _cfg(cfg)
            store.has_user.return_value = False
            _mw()._maybe_provision_bearer_user("a@x.com", "tok", {"groups": ["mlflow-admins"]})

        create_user.assert_not_called()


class TestGroupsAreWrittenAsLoginWritesThem:
    """Bearer provisioning writes the membership interactive login would: namespaced per provider,
    and following the provider's group_sync."""

    def _provision(self, monkeypatch, provider, groups):
        import mlflow_oidc_auth.auth as auth_module

        monkeypatch.setattr(auth_module, "resolve_token_provider", lambda token: provider)
        with (
            patch("mlflow_oidc_auth.middleware.auth_middleware.config") as cfg,
            patch("mlflow_oidc_auth.middleware.auth_middleware.store") as store,
            patch("mlflow_oidc_auth.user.create_user") as create_user,
            patch("mlflow_oidc_auth.user.populate_groups", return_value=[]) as populate_groups,
            patch("mlflow_oidc_auth.user.update_user") as update_user,
        ):
            _cfg(cfg)
            store.has_user.return_value = False
            _mw()._maybe_provision_bearer_user("a@x.com", "tok", {"groups": groups})
        return create_user, populate_groups, update_user

    def test_another_providers_groups_are_namespaced(self, monkeypatch):
        _, populate_groups, update_user = self._provision(monkeypatch, _provider(id="partner"), ["mlflow-users", "finance-ds"])

        populate_groups.assert_called_once_with(group_names=["partner:mlflow-users", "partner:finance-ds"], written_by="oidc:partner")
        update_user.assert_called_once_with(username="a@x.com", group_names=["partner:mlflow-users", "partner:finance-ds"], written_by="oidc:partner")

    def test_the_deployments_own_provider_keeps_raw_names(self, monkeypatch):
        _, populate_groups, _ = self._provision(monkeypatch, _provider(), ["mlflow-users"])

        populate_groups.assert_called_once_with(group_names=["mlflow-users"], written_by="oidc:default")

    def test_a_provider_that_syncs_no_groups_writes_none(self, monkeypatch):
        create_user, populate_groups, update_user = self._provision(monkeypatch, _provider(id="partner", group_sync="none"), ["mlflow-users"])

        create_user.assert_called_once()
        populate_groups.assert_not_called()
        update_user.assert_not_called()

    def test_a_provider_that_does_not_create_users_at_login_does_not_here(self, monkeypatch):
        create_user, _, _ = self._provision(monkeypatch, _provider(id="partner", provisioning="scim"), ["mlflow-users"])

        create_user.assert_not_called()

    def test_groups_this_created_get_their_workspace_rules(self, monkeypatch):
        import mlflow_oidc_auth.auth as auth_module

        monkeypatch.setattr(auth_module, "resolve_token_provider", lambda token: _provider(id="partner"))
        with (
            patch("mlflow_oidc_auth.middleware.auth_middleware.config") as cfg,
            patch("mlflow_oidc_auth.middleware.auth_middleware.store") as store,
            patch("mlflow_oidc_auth.user.create_user"),
            patch("mlflow_oidc_auth.user.populate_groups", return_value=["partner:mlflow-users"]),
            patch("mlflow_oidc_auth.user.update_user"),
            patch("mlflow_oidc_auth.workspace_rules.apply_rules_for_groups") as apply_rules,
        ):
            _cfg(cfg)
            store.has_user.return_value = False
            _mw()._maybe_provision_bearer_user("a@x.com", "tok", {"groups": ["mlflow-users"]})

        apply_rules.assert_called_once_with(["partner:mlflow-users"], source="oidc:partner")
