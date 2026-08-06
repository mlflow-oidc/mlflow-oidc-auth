"""OIDC_USERNAME_FIELD/OIDC_DISPLAY_NAME_FIELD must not be silently unusable.

A field list with no usable entry means no claim can ever match, so every OIDC login
(and, for OIDC_USERNAME_FIELD, every bearer-token authentication too) would fail for
every user. Unlike a merely-loose default, this leaves the deployment fully unable to
authenticate anyone — so the app refuses to start rather than coming up looking healthy.
"""

from unittest.mock import MagicMock, patch

import pytest

from mlflow_oidc_auth import config as config_module


def _validate(username_field, display_name_field):
    """Run the check in isolation against a stub config, raising like the real method would."""
    stub = MagicMock()
    stub.OIDC_USERNAME_FIELD = username_field
    stub.OIDC_DISPLAY_NAME_FIELD = display_name_field

    config_module.AppConfig._validate_username_field_configured(stub)


class TestUnusableFieldsRefuseToStart:
    """A field list with no non-blank entry must raise, not just warn."""

    def test_empty_username_field_raises(self):
        """An empty OIDC_USERNAME_FIELD list must raise ValueError."""
        with pytest.raises(ValueError, match="OIDC_USERNAME_FIELD is empty"):
            _validate(username_field=[], display_name_field=["name"])

    def test_empty_display_name_field_raises(self):
        """An empty OIDC_DISPLAY_NAME_FIELD list must raise ValueError."""
        with pytest.raises(ValueError, match="OIDC_DISPLAY_NAME_FIELD is empty"):
            _validate(username_field=["email"], display_name_field=[])

    def test_blank_string_only_username_field_raises(self):
        """OIDC_USERNAME_FIELD="" becomes [""] via get_list, not []; that must still raise."""
        with pytest.raises(ValueError, match="OIDC_USERNAME_FIELD is empty"):
            _validate(username_field=[""], display_name_field=["name"])

    def test_whitespace_only_username_field_raises(self):
        """A field list containing only whitespace entries is just as unusable as an empty one."""
        with pytest.raises(ValueError, match="OIDC_USERNAME_FIELD is empty"):
            _validate(username_field=["  ", "\t"], display_name_field=["name"])

    def test_username_checked_before_display_name(self):
        """When both are unusable, the username error surfaces first (it is the more severe outage)."""
        with pytest.raises(ValueError, match="OIDC_USERNAME_FIELD is empty"):
            _validate(username_field=[], display_name_field=[])


class TestUsableFieldsAreSilent:
    """Any field list with at least one non-blank entry must not raise."""

    def test_defaults_are_silent(self):
        """The shipped defaults must never trip this check."""
        _validate(username_field=["email", "preferred_username"], display_name_field=["name"])

    def test_custom_non_empty_fields_are_silent(self):
        """A fully custom, non-empty configuration must not raise."""
        _validate(username_field=["sub"], display_name_field=["full_name"])

    def test_a_usable_entry_after_blank_entries_is_silent(self):
        """A mix of blank and usable entries only needs one usable entry to be valid."""
        _validate(username_field=["", "  ", "sub"], display_name_field=["name"])


def test_the_check_runs_during_config_construction():
    """Wiring: the validation is useless if nothing calls it."""
    with patch.object(config_module.AppConfig, "_validate_username_field_configured") as check:
        config_module.AppConfig()

    check.assert_called_once()
