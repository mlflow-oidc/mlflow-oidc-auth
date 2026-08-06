"""OIDC_USERNAME_FIELD/OIDC_DISPLAY_NAME_FIELD must not be silently misconfigured.

An empty list means no field can ever be found, so every login and every bearer-token
authentication would fail. That failure only surfaces on the first real login attempt in
production — warn at startup instead so a typo'd or emptied config value is caught early.
"""

from unittest.mock import MagicMock, patch

from mlflow_oidc_auth import config as config_module


def _warn_for(username_field, display_name_field):
    """Run the check in isolation against a stub config, returning the warnings issued."""
    stub = MagicMock()
    stub.OIDC_USERNAME_FIELD = username_field
    stub.OIDC_DISPLAY_NAME_FIELD = display_name_field

    with patch.object(config_module, "logger") as logger:
        config_module.AppConfig._warn_if_username_field_misconfigured(stub)

    return [call.args[0] for call in logger.warning.call_args_list]


class TestMisconfiguredFieldsWarn:
    def test_empty_username_field_warns(self):
        warnings = _warn_for(username_field=[], display_name_field=["name"])
        assert any("OIDC_USERNAME_FIELD is empty" in w for w in warnings)

    def test_empty_display_name_field_warns(self):
        warnings = _warn_for(username_field=["email"], display_name_field=[])
        assert any("OIDC_DISPLAY_NAME_FIELD is empty" in w for w in warnings)

    def test_both_empty_warns_twice(self):
        warnings = _warn_for(username_field=[], display_name_field=[])
        assert len(warnings) == 2


class TestConfiguredFieldsAreSilent:
    def test_defaults_are_silent(self):
        assert _warn_for(username_field=["email", "preferred_username"], display_name_field=["name"]) == []

    def test_custom_non_empty_fields_are_silent(self):
        assert _warn_for(username_field=["sub"], display_name_field=["full_name"]) == []


def test_the_check_runs_during_config_construction():
    """Wiring: the warning is useless if nothing calls it."""
    with patch.object(config_module.AppConfig, "_warn_if_username_field_misconfigured") as check:
        config_module.AppConfig()

    check.assert_called_once()
