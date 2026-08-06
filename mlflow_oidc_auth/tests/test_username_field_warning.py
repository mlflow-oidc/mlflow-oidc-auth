"""OIDC_USERNAME_FIELD/OIDC_DISPLAY_NAME_FIELD must not be silently unusable.

A field list with no usable entry means no claim can ever match, so every OIDC login
(and, for OIDC_USERNAME_FIELD, every bearer-token authentication too) would fail for
every user. That failure only surfaces on the first real login attempt in production —
warn at startup instead so a typo'd or emptied config value is caught early.

This warns rather than raises: AppConfig() is a module-level singleton imported by
tooling that has nothing to do with OIDC login (e.g. the Alembic migration environment),
so raising here would take that unrelated tooling down too. See the docstring on
_warn_if_username_field_unusable for the full reasoning and precedent.
"""

import os
from unittest.mock import MagicMock, patch

from mlflow_oidc_auth import config as config_module


def _warn_for(username_field, display_name_field):
    """Run the check in isolation against a stub config, returning the warnings issued."""
    stub = MagicMock()
    stub.OIDC_USERNAME_FIELD = username_field
    stub.OIDC_DISPLAY_NAME_FIELD = display_name_field

    with patch.object(config_module, "logger") as logger:
        config_module.AppConfig._warn_if_username_field_unusable(stub)

    return [call.args[0] for call in logger.warning.call_args_list]


class TestUnusableFieldsWarn:
    """A field list with no non-blank, string entry must produce a warning."""

    def test_empty_username_field_warns(self):
        """An empty OIDC_USERNAME_FIELD list must warn."""
        warnings = _warn_for(username_field=[], display_name_field=["name"])
        assert any("OIDC_USERNAME_FIELD is empty" in w for w in warnings)

    def test_empty_display_name_field_warns(self):
        """An empty OIDC_DISPLAY_NAME_FIELD list must warn."""
        warnings = _warn_for(username_field=["email"], display_name_field=[])
        assert any("OIDC_DISPLAY_NAME_FIELD is empty" in w for w in warnings)

    def test_both_empty_warns_twice(self):
        """Both fields unusable at once must produce two separate warnings."""
        warnings = _warn_for(username_field=[], display_name_field=[])
        assert len(warnings) == 2

    def test_blank_string_only_username_field_warns(self):
        """OIDC_USERNAME_FIELD="" becomes [""] via get_list, not []; that must still warn."""
        warnings = _warn_for(username_field=[""], display_name_field=["name"])
        assert any("OIDC_USERNAME_FIELD is empty" in w for w in warnings)

    def test_whitespace_only_username_field_warns(self):
        """A field list containing only whitespace entries is just as unusable as an empty one."""
        warnings = _warn_for(username_field=["  ", "\t"], display_name_field=["name"])
        assert any("OIDC_USERNAME_FIELD is empty" in w for w in warnings)

    def test_non_string_entry_is_treated_as_unusable_not_a_crash(self):
        """A non-string entry (e.g. from malformed secret-provider JSON) must warn, not raise."""
        warnings = _warn_for(username_field=["", None, 123], display_name_field=["name"])
        assert any("OIDC_USERNAME_FIELD is empty" in w for w in warnings)


class TestUsableFieldsAreSilent:
    """Any field list with at least one non-blank string entry must not warn."""

    def test_defaults_are_silent(self):
        """The shipped defaults must never trip this check."""
        assert _warn_for(username_field=["email", "preferred_username"], display_name_field=["name"]) == []

    def test_custom_non_empty_fields_are_silent(self):
        """A fully custom, non-empty configuration must not warn."""
        assert _warn_for(username_field=["sub"], display_name_field=["full_name"]) == []

    def test_a_usable_entry_after_blank_entries_is_silent(self):
        """A mix of blank and usable entries only needs one usable entry to be valid."""
        assert _warn_for(username_field=["", "  ", "sub"], display_name_field=["name"]) == []


def test_the_check_runs_during_config_construction():
    """Wiring: the warning is useless if nothing calls it."""
    with patch.object(config_module.AppConfig, "_warn_if_username_field_unusable") as check:
        config_module.AppConfig()

    check.assert_called_once()


def test_real_construction_with_empty_username_field_does_not_raise():
    """Regression guard: AppConfig() must not raise for OIDC-unrelated importers (e.g. Alembic).

    OIDC_USERNAME_FIELD="" resolves to [""] via get_list, the exact case a prior
    revision of this check mistakenly raised ValueError for, which would have taken
    down any tooling that merely imports mlflow_oidc_auth.config (db/migrations/env.py
    does this at module scope for an unrelated Alembic workflow).
    """
    with patch.dict(os.environ, {"OIDC_USERNAME_FIELD": "", "OIDC_DISPLAY_NAME_FIELD": ""}):
        config_module.AppConfig()  # must not raise
