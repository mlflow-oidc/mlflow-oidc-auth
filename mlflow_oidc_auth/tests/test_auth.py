from unittest.mock import MagicMock, patch

import pytest
from authlib.jose.errors import BadSignatureError

from mlflow_oidc_auth.auth import (
    _get_oidc_jwks,
    validate_token,
)


class TestAuth:
    @patch("mlflow_oidc_auth.auth.requests")
    @patch("mlflow_oidc_auth.auth.config")
    def test_get_oidc_jwks_success(self, mock_config, mock_requests):
        """Test successful JWKS retrieval from OIDC provider"""
        mock_config.OIDC_DISCOVERY_URL = "https://example.com/.well-known/openid_configuration"

        # Mock discovery document response
        discovery_response = MagicMock()
        discovery_response.json.return_value = {"jwks_uri": "https://example.com/jwks"}

        # Mock JWKS response
        jwks_response = MagicMock()
        jwks_response.json.return_value = {"keys": [{"kty": "RSA", "kid": "test"}]}

        mock_requests.get.side_effect = [discovery_response, jwks_response]

        result = _get_oidc_jwks()

        # Verify requests were made correctly
        assert mock_requests.get.call_count == 2
        mock_requests.get.assert_any_call("https://example.com/.well-known/openid_configuration")
        mock_requests.get.assert_any_call("https://example.com/jwks")

        assert result == {"keys": [{"kty": "RSA", "kid": "test"}]}

    @patch("mlflow_oidc_auth.auth.config")
    def test_get_oidc_jwks_no_discovery_url(self, mock_config):
        """Test JWKS retrieval fails when OIDC_DISCOVERY_URL is not set"""
        mock_config.OIDC_DISCOVERY_URL = None

        with pytest.raises(ValueError, match="OIDC_DISCOVERY_URL is not set in the configuration"):
            _get_oidc_jwks()

    @patch("mlflow_oidc_auth.auth._get_oidc_jwks")
    @patch("mlflow_oidc_auth.auth.jwt.decode")
    def test_validate_token_success(self, mock_jwt_decode, mock_get_oidc_jwks):
        """Test successful token validation"""
        mock_jwks = {"keys": [{"kty": "RSA", "kid": "test"}]}
        mock_get_oidc_jwks.return_value = mock_jwks
        mock_payload = MagicMock()
        mock_jwt_decode.return_value = mock_payload

        result = validate_token("valid_token")

        mock_jwt_decode.assert_called_once_with("valid_token", mock_jwks)
        mock_payload.validate.assert_called_once()
        assert result == mock_payload

    @patch("mlflow_oidc_auth.auth._get_oidc_jwks")
    @patch("mlflow_oidc_auth.auth.jwt.decode")
    def test_validate_token_bad_signature_then_success(self, mock_jwt_decode, mock_get_oidc_jwks):
        """Test token validation with bad signature that succeeds after JWKS refresh"""
        mock_get_oidc_jwks.side_effect = [{"keys": "old_jwks"}, {"keys": "new_jwks"}]
        mock_payload = MagicMock()
        mock_jwt_decode.side_effect = [BadSignatureError("bad signature"), mock_payload]

        result = validate_token("token_with_new_key")

        assert result == mock_payload
        assert mock_get_oidc_jwks.call_count == 2
        # JWKS is re-fetched on the second attempt
        mock_get_oidc_jwks.assert_any_call()

    @patch("mlflow_oidc_auth.auth._get_oidc_jwks")
    @patch("mlflow_oidc_auth.auth.jwt.decode")
    def test_validate_token_bad_signature_after_refresh(self, mock_jwt_decode, mock_get_oidc_jwks):
        """Test token validation that fails even after JWKS refresh"""
        mock_get_oidc_jwks.side_effect = [{"keys": "old_jwks"}, {"keys": "new_jwks"}]
        mock_jwt_decode.side_effect = [BadSignatureError("bad signature"), BadSignatureError("still bad")]

        with pytest.raises(BadSignatureError):
            validate_token("invalid_token")

        assert mock_get_oidc_jwks.call_count == 2

    @patch("mlflow_oidc_auth.auth._get_oidc_jwks")
    @patch("mlflow_oidc_auth.auth.jwt.decode")
    def test_validate_token_unexpected_error_after_refresh(self, mock_jwt_decode, mock_get_oidc_jwks):
        """Test token validation with unexpected error after JWKS refresh"""
        mock_get_oidc_jwks.side_effect = [{"keys": "old_jwks"}, {"keys": "new_jwks"}]
        mock_jwt_decode.side_effect = [BadSignatureError("bad signature"), ValueError("unexpected error")]

        with pytest.raises(ValueError, match="unexpected error"):
            validate_token("problematic_token")

        assert mock_get_oidc_jwks.call_count == 2
