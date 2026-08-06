"""
Tests for OIDC field extraction utilities.

Tests verify that the extract_username and extract_display_name functions
correctly handle configurable fields and fallback logic.
"""

from unittest.mock import patch

import pytest

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.utils.oidc_field_extraction import (
    extract_field_from_payload,
    extract_username,
    extract_display_name,
)


class TestExtractFieldFromPayload:
    """Tests for extract_field_from_payload utility function."""

    def test_extract_first_field_success(self):
        """Test extracting the first configured field when it exists."""
        payload = {"email": "user@example.com", "preferred_username": "user"}
        value, error = extract_field_from_payload(payload, ["email", "preferred_username"], "username")
        assert value == "user@example.com"
        assert error is None

    def test_extract_fallback_field_success(self):
        """Test falling back to second field when first doesn't exist."""
        payload = {"preferred_username": "user"}
        value, error = extract_field_from_payload(payload, ["email", "preferred_username"], "username")
        assert value == "user"
        assert error is None

    def test_extract_no_field_found(self):
        """Test error when none of the configured fields exist."""
        payload = {"name": "John"}
        value, error = extract_field_from_payload(payload, ["email", "preferred_username"], "username")
        assert value is None
        assert "No username provided in OIDC userinfo" in error

    def test_extract_field_non_string_value(self):
        """Test error when field value is not a string."""
        payload = {"email": 123}
        value, error = extract_field_from_payload(payload, ["email"], "username")
        assert value is None
        assert "Invalid OIDC username field: email is not a string" in error

    def test_extract_empty_field_list(self):
        """Test error when no fields are configured."""
        payload = {"email": "user@example.com"}
        value, error = extract_field_from_payload(payload, [], "username")
        assert value is None
        assert "No username fields configured" in error

    def test_extract_empty_string_value_falls_back_to_next_field(self):
        """Test that an empty-string field value is treated as missing, not as found."""
        payload = {"email": "", "preferred_username": "alice"}
        value, error = extract_field_from_payload(payload, ["email", "preferred_username"], "username")
        assert value == "alice"
        assert error is None

    def test_extract_all_empty_string_values_errors(self):
        """Test that an all-empty-string payload reports an error rather than a blank value."""
        payload = {"email": "", "preferred_username": ""}
        value, error = extract_field_from_payload(payload, ["email", "preferred_username"], "username")
        assert value is None
        assert "No username provided in OIDC userinfo" in error

    def test_extract_custom_source_in_error_message(self):
        """Test that the source description is used in the 'not found' error message."""
        payload = {}
        value, error = extract_field_from_payload(payload, ["email"], "username", source="bearer token payload")
        assert value is None
        assert "No username provided in bearer token payload" in error

    def test_extract_field_type_name_underscore_humanized(self):
        """Test that an underscore in field_type_name is rendered as a space in messages."""
        payload = {}
        value, error = extract_field_from_payload(payload, ["name"], "display_name")
        assert value is None
        assert "No display name provided in OIDC userinfo" in error

    def test_extract_whitespace_only_value_falls_back_to_next_field(self):
        """Test that a whitespace-only field value is treated as missing, not as found."""
        payload = {"email": "   ", "preferred_username": "alice"}
        value, error = extract_field_from_payload(payload, ["email", "preferred_username"], "username")
        assert value == "alice"
        assert error is None

    def test_extract_all_whitespace_only_values_errors(self):
        """Test that whitespace-only values across every field report an error, not a blank value."""
        payload = {"email": "   ", "preferred_username": "\t"}
        value, error = extract_field_from_payload(payload, ["email", "preferred_username"], "username")
        assert value is None
        assert "No username provided in OIDC userinfo" in error

    def test_extract_falsy_non_string_value_still_reports_type_error(self):
        """Test that a present-but-falsy non-string value (e.g. 0) still gets the type-error diagnostic."""
        payload = {"email": 0}
        value, error = extract_field_from_payload(payload, ["email"], "username")
        assert value is None
        assert "Invalid OIDC username field: email is not a string" in error

    def test_extract_false_value_still_reports_type_error(self):
        """Test that a boolean False value still gets the type-error diagnostic rather than being skipped."""
        payload = {"email": False}
        value, error = extract_field_from_payload(payload, ["email"], "username")
        assert value is None
        assert "Invalid OIDC username field: email is not a string" in error


class TestExtractUsername:
    """Tests for extract_username utility function."""

    def test_extract_username_from_email(self, monkeypatch):
        """Test extracting username from email field."""
        monkeypatch.setattr(config, "OIDC_USERNAME_FIELD", ["email", "preferred_username"])
        payload = {"email": "User@Example.COM"}
        username, error = extract_username(payload)
        assert username == "user@example.com"  # Should be lowercased
        assert error is None

    def test_extract_username_from_preferred_username(self, monkeypatch):
        """Test extracting username from preferred_username field as fallback."""
        monkeypatch.setattr(config, "OIDC_USERNAME_FIELD", ["email", "preferred_username"])
        payload = {"preferred_username": "John.Doe"}
        username, error = extract_username(payload)
        assert username == "john.doe"  # Should be lowercased
        assert error is None

    def test_extract_username_missing(self, monkeypatch):
        """Test error when username fields are missing."""
        monkeypatch.setattr(config, "OIDC_USERNAME_FIELD", ["email", "preferred_username"])
        payload = {"name": "John"}
        username, error = extract_username(payload)
        assert username is None
        assert "No username provided in OIDC userinfo" in error

    def test_extract_username_non_string(self, monkeypatch):
        """Test error when username field is not a string."""
        monkeypatch.setattr(config, "OIDC_USERNAME_FIELD", ["email"])
        payload = {"email": ["user@example.com"]}
        username, error = extract_username(payload)
        assert username is None
        assert "Invalid OIDC username field" in error

    def test_extract_username_empty_string_is_not_a_valid_username(self, monkeypatch):
        """Test that an empty-string field value never yields a None username with no error."""
        monkeypatch.setattr(config, "OIDC_USERNAME_FIELD", ["email", "preferred_username"])
        payload = {"email": "", "preferred_username": ""}
        username, error = extract_username(payload)
        assert username is None
        assert error is not None

    def test_extract_username_custom_source(self, monkeypatch):
        """Test that a custom source is reflected in the error message."""
        monkeypatch.setattr(config, "OIDC_USERNAME_FIELD", ["email"])
        username, error = extract_username({}, source="bearer token payload")
        assert username is None
        assert "bearer token payload" in error

    def test_extract_username_delegates_to_normalize_username(self, monkeypatch):
        """Test that username normalization reuses the codebase's canonical normalizer."""
        monkeypatch.setattr(config, "OIDC_USERNAME_FIELD", ["email"])
        with patch("mlflow_oidc_auth.utils.oidc_field_extraction.normalize_username", return_value="normalized") as mock_normalize:
            username, error = extract_username({"email": "User@Example.COM"})
        mock_normalize.assert_called_once_with("User@Example.COM")
        assert username == "normalized"
        assert error is None


class TestExtractDisplayName:
    """Tests for extract_display_name utility function."""

    def test_extract_display_name_success(self, monkeypatch):
        """Test extracting display name from name field."""
        monkeypatch.setattr(config, "OIDC_DISPLAY_NAME_FIELD", ["name"])
        payload = {"name": "John Doe"}
        display_name, error = extract_display_name(payload)
        assert display_name == "John Doe"
        assert error is None

    def test_extract_display_name_missing(self, monkeypatch):
        """Test error when display name field is missing."""
        monkeypatch.setattr(config, "OIDC_DISPLAY_NAME_FIELD", ["name"])
        payload = {"email": "user@example.com"}
        display_name, error = extract_display_name(payload)
        assert display_name is None
        assert "No display name provided in OIDC userinfo" in error

    def test_extract_display_name_non_string(self, monkeypatch):
        """Test error when display name field is not a string."""
        monkeypatch.setattr(config, "OIDC_DISPLAY_NAME_FIELD", ["name"])
        payload = {"name": {"first": "John", "last": "Doe"}}
        display_name, error = extract_display_name(payload)
        assert display_name is None
        assert "Invalid OIDC display name field" in error

    def test_extract_display_name_fallback(self, monkeypatch):
        """Test falling back to alternative display name field."""
        monkeypatch.setattr(config, "OIDC_DISPLAY_NAME_FIELD", ["name", "given_name"])
        payload = {"given_name": "John"}
        display_name, error = extract_display_name(payload)
        assert display_name == "John"
        assert error is None
