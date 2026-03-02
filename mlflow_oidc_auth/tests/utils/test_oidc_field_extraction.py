"""
Tests for OIDC field extraction utilities.

Tests verify that the extract_username and extract_display_name functions
correctly handle configurable fields and fallback logic.
"""

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
        assert "No display_name provided in OIDC userinfo" in error

    def test_extract_display_name_non_string(self, monkeypatch):
        """Test error when display name field is not a string."""
        monkeypatch.setattr(config, "OIDC_DISPLAY_NAME_FIELD", ["name"])
        payload = {"name": {"first": "John", "last": "Doe"}}
        display_name, error = extract_display_name(payload)
        assert display_name is None
        assert "Invalid OIDC display_name field" in error

    def test_extract_display_name_fallback(self, monkeypatch):
        """Test falling back to alternative display name field."""
        monkeypatch.setattr(config, "OIDC_DISPLAY_NAME_FIELD", ["name", "given_name"])
        payload = {"given_name": "John"}
        display_name, error = extract_display_name(payload)
        assert display_name == "John"
        assert error is None

