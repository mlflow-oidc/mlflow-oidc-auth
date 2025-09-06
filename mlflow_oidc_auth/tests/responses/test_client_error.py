import pytest
import json
from flask import Flask, jsonify
from unittest.mock import patch, MagicMock
from mlflow_oidc_auth.responses.client_error import (
    make_auth_required_response,
    make_forbidden_response,
    make_basic_auth_response,
)


@pytest.fixture(scope="module")
def test_app():
    app = Flask(__name__)
    with app.app_context():
        yield app


class TestClientErrorResponses:
    def test_make_auth_required_response(self, test_app):
        response = make_auth_required_response()
        assert response.status_code == 401
        assert response.get_json() == {"message": "Authentication required"}

    def test_make_forbidden_response(self, test_app):
        response = make_forbidden_response()
        assert response.status_code == 403
        assert response.get_json() == {"message": "Permission denied"}

    def test_make_forbidden_response_custom_message(self, test_app):
        custom_msg = {"message": "Custom permission denied message"}
        response = make_forbidden_response(custom_msg)
        assert response.status_code == 403
        assert response.get_json() == custom_msg

    def test_make_basic_auth_response(self, test_app):
        response = make_basic_auth_response()
        assert response.status_code == 401
        assert response.data.decode() == ("You are not authenticated. Please see documentation for details" "https://github.com/mlflow-oidc/mlflow-oidc-auth")
        assert response.headers["WWW-Authenticate"] == 'Basic realm="mlflow"'


class TestClientErrorResponseSecurity:
    """Test security aspects of client error responses."""

    def test_auth_required_response_security_headers(self, test_app):
        """Test that auth required response has appropriate security characteristics."""
        response = make_auth_required_response()

        # Verify response is JSON and properly formatted
        assert response.content_type == "application/json"
        assert response.status_code == 401

        # Verify response doesn't leak sensitive information
        response_data = response.get_json()
        assert "message" in response_data
        assert len(response_data) == 1  # Only contains expected message

        # Verify message is safe and doesn't contain sensitive data
        assert "Authentication required" in response_data["message"]
        assert "password" not in response_data["message"].lower()
        assert "token" not in response_data["message"].lower()
        assert "secret" not in response_data["message"].lower()

    def test_forbidden_response_security_headers(self, test_app):
        """Test that forbidden response has appropriate security characteristics."""
        response = make_forbidden_response()

        # Verify response is JSON and properly formatted
        assert response.content_type == "application/json"
        assert response.status_code == 403

        # Verify response doesn't leak sensitive information
        response_data = response.get_json()
        assert "message" in response_data
        assert len(response_data) == 1  # Only contains expected message

        # Verify message is safe and doesn't contain sensitive data
        assert "Permission denied" in response_data["message"]
        assert "password" not in response_data["message"].lower()
        assert "token" not in response_data["message"].lower()
        assert "secret" not in response_data["message"].lower()

    def test_basic_auth_response_security_headers(self, test_app):
        """Test that basic auth response has appropriate security characteristics."""
        response = make_basic_auth_response()

        # Verify response has proper WWW-Authenticate header
        assert "WWW-Authenticate" in response.headers
        assert response.headers["WWW-Authenticate"] == 'Basic realm="mlflow"'

        # Verify response doesn't leak sensitive information
        response_text = response.data.decode()
        assert "password" not in response_text.lower()
        assert "token" not in response_text.lower()
        assert "secret" not in response_text.lower()

        # Verify it contains helpful documentation link
        assert "https://github.com/mlflow-oidc/mlflow-oidc-auth" in response_text

    def test_forbidden_response_custom_message_sanitization(self, test_app):
        """Test that custom messages in forbidden responses are properly handled."""
        # Test with potentially dangerous custom message
        dangerous_msg = {"message": "Access denied", "debug_info": "Internal server details", "user_id": "12345"}

        response = make_forbidden_response(dangerous_msg)
        assert response.status_code == 403

        # Verify the entire custom message is preserved (responsibility of caller to sanitize)
        response_data = response.get_json()
        assert response_data == dangerous_msg

    def test_forbidden_response_with_none_message(self, test_app):
        """Test forbidden response when explicitly passed None."""
        response = make_forbidden_response(None)
        assert response.status_code == 403
        assert response.get_json() == {"message": "Permission denied"}

    def test_forbidden_response_with_empty_dict(self, test_app):
        """Test forbidden response with empty dictionary."""
        response = make_forbidden_response({})
        assert response.status_code == 403
        assert response.get_json() == {}


class TestClientErrorResponseConsistency:
    """Test consistency and user experience aspects of error responses."""

    def test_response_format_consistency(self, test_app):
        """Test that all JSON responses follow consistent format."""
        auth_response = make_auth_required_response()
        forbidden_response = make_forbidden_response()

        # Both should be JSON responses
        assert auth_response.content_type == "application/json"
        assert forbidden_response.content_type == "application/json"

        # Both should have message field in default case
        auth_data = auth_response.get_json()
        forbidden_data = forbidden_response.get_json()

        assert "message" in auth_data
        assert "message" in forbidden_data
        assert isinstance(auth_data["message"], str)
        assert isinstance(forbidden_data["message"], str)

    def test_status_code_consistency(self, test_app):
        """Test that status codes are consistent with HTTP standards."""
        auth_response = make_auth_required_response()
        forbidden_response = make_forbidden_response()
        basic_auth_response = make_basic_auth_response()

        # Verify correct HTTP status codes
        assert auth_response.status_code == 401  # Unauthorized
        assert forbidden_response.status_code == 403  # Forbidden
        assert basic_auth_response.status_code == 401  # Unauthorized (with WWW-Authenticate)

    def test_error_message_clarity(self, test_app):
        """Test that error messages are clear and helpful."""
        auth_response = make_auth_required_response()
        forbidden_response = make_forbidden_response()
        basic_auth_response = make_basic_auth_response()

        # Verify messages are clear and actionable
        auth_data = auth_response.get_json()
        forbidden_data = forbidden_response.get_json()
        basic_text = basic_auth_response.data.decode()

        assert "Authentication required" in auth_data["message"]
        assert "Permission denied" in forbidden_data["message"]
        assert "not authenticated" in basic_text
        assert "documentation" in basic_text


class TestClientErrorResponseSerialization:
    """Test response serialization and content negotiation."""

    def test_json_serialization_auth_required(self, test_app):
        """Test JSON serialization for auth required response."""
        response = make_auth_required_response()

        # Verify response can be serialized to JSON
        json_data = response.get_json()
        assert json_data is not None

        # Verify JSON is valid by re-serializing
        json_string = json.dumps(json_data)
        assert json_string is not None

        # Verify deserialization works
        deserialized = json.loads(json_string)
        assert deserialized == json_data

    def test_json_serialization_forbidden(self, test_app):
        """Test JSON serialization for forbidden response."""
        response = make_forbidden_response()

        # Verify response can be serialized to JSON
        json_data = response.get_json()
        assert json_data is not None

        # Verify JSON is valid by re-serializing
        json_string = json.dumps(json_data)
        assert json_string is not None

        # Verify deserialization works
        deserialized = json.loads(json_string)
        assert deserialized == json_data

    def test_json_serialization_custom_message(self, test_app):
        """Test JSON serialization with custom message."""
        custom_msg = {"message": "Custom error", "code": "ERR_001", "details": {"field": "value"}}

        response = make_forbidden_response(custom_msg)

        # Verify response can be serialized to JSON
        json_data = response.get_json()
        assert json_data is not None

        # Verify JSON is valid by re-serializing
        json_string = json.dumps(json_data)
        assert json_string is not None

        # Verify deserialization works and preserves structure
        deserialized = json.loads(json_string)
        assert deserialized == custom_msg

    def test_content_type_headers(self, test_app):
        """Test that content type headers are set correctly."""
        auth_response = make_auth_required_response()
        forbidden_response = make_forbidden_response()
        basic_auth_response = make_basic_auth_response()

        # JSON responses should have application/json content type
        assert auth_response.content_type == "application/json"
        assert forbidden_response.content_type == "application/json"

        # Basic auth response should have text/html content type (Flask default for string)
        assert basic_auth_response.content_type == "text/html; charset=utf-8"

    def test_response_encoding(self, test_app):
        """Test that responses are properly encoded."""
        auth_response = make_auth_required_response()
        forbidden_response = make_forbidden_response()
        basic_auth_response = make_basic_auth_response()

        # Verify responses can be decoded without errors
        auth_data = auth_response.data.decode("utf-8")
        forbidden_data = forbidden_response.data.decode("utf-8")
        basic_data = basic_auth_response.data.decode("utf-8")

        assert auth_data is not None
        assert forbidden_data is not None
        assert basic_data is not None

        # Verify JSON responses contain valid JSON
        json.loads(auth_data)  # Should not raise exception
        json.loads(forbidden_data)  # Should not raise exception


class TestClientErrorResponseEdgeCases:
    """Test edge cases and error conditions."""

    def test_forbidden_response_with_non_dict_message(self, test_app):
        """Test forbidden response with non-dictionary message."""
        # Test with string message
        response = make_forbidden_response("String message")
        assert response.status_code == 403
        assert response.get_json() == "String message"

        # Test with list message
        response = make_forbidden_response(["item1", "item2"])
        assert response.status_code == 403
        assert response.get_json() == ["item1", "item2"]

        # Test with number message
        response = make_forbidden_response(42)
        assert response.status_code == 403
        assert response.get_json() == 42

    def test_response_immutability(self, test_app):
        """Test that responses are properly constructed and immutable."""
        response1 = make_auth_required_response()
        response2 = make_auth_required_response()

        # Responses should be independent instances
        assert response1 is not response2
        assert response1.status_code == response2.status_code
        assert response1.get_json() == response2.get_json()

    @patch("mlflow_oidc_auth.responses.client_error.make_response")
    def test_make_response_error_handling(self, mock_make_response, test_app):
        """Test error handling when make_response fails."""
        mock_make_response.side_effect = Exception("Flask error")

        with pytest.raises(Exception, match="Flask error"):
            make_auth_required_response()

    @patch("mlflow_oidc_auth.responses.client_error.jsonify")
    def test_jsonify_error_handling(self, mock_jsonify, test_app):
        """Test error handling when jsonify fails."""
        mock_jsonify.side_effect = Exception("JSON error")

        with pytest.raises(Exception, match="JSON error"):
            make_auth_required_response()

    def test_large_custom_message_handling(self, test_app):
        """Test handling of large custom messages."""
        large_message = {"message": "A" * 10000, "details": "B" * 5000}  # Large message

        response = make_forbidden_response(large_message)
        assert response.status_code == 403

        # Verify large message is handled correctly
        response_data = response.get_json()
        assert response_data["message"] == "A" * 10000
        assert response_data["details"] == "B" * 5000
