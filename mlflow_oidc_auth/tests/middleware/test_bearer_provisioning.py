"""Layer 2 of the #262 fix: opt-in, hardened auto-provisioning on bearer authentication."""

from unittest.mock import MagicMock, patch

import pytest

from mlflow_oidc_auth.middleware.auth_middleware import AuthMiddleware


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
            create_user.assert_called_once_with(username="a@x.com", display_name="Alice", is_admin=False)
            populate_groups.assert_called_once_with(group_names=["mlflow-users"])
            update_user.assert_called_once_with(username="a@x.com", group_names=["mlflow-users"])


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
            create_user.assert_called_once_with(username="a@x.com", display_name="a@x.com", is_admin=False)

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
            create_user.assert_called_once_with(username="a@x.com", display_name="a@x.com", is_admin=True)


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
            populate_groups.assert_called_once_with(group_names=["mlflow-users"])

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
