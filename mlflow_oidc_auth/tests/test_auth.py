from unittest.mock import MagicMock, patch

import pytest
from authlib.jose.errors import BadSignatureError

from mlflow_oidc_auth.auth import (
    _claims_options_for,
    _get_oidc_jwks,
    _jwks_cache,
    validate_token,
)


@pytest.fixture(autouse=True)
def clear_jwks_cache():
    """Clear the JWKS cache before each test to prevent cross-test contamination."""
    _jwks_cache.clear()
    yield
    _jwks_cache.clear()


class TestGetOidcJwks:
    """Test _get_oidc_jwks with caching behavior."""

    @patch("mlflow_oidc_auth.auth.requests")
    @patch("mlflow_oidc_auth.auth.config")
    def test_get_oidc_jwks_success(self, mock_config, mock_requests):
        """Test successful JWKS retrieval from OIDC provider"""
        mock_config.OIDC_DISCOVERY_URL = "https://example.com/.well-known/openid_configuration"
        mock_config.OIDC_HTTP_TIMEOUT_SECONDS = 10
        mock_config.OIDC_VERIFY_SSL = True

        discovery_response = MagicMock()
        discovery_response.json.return_value = {"jwks_uri": "https://example.com/jwks"}
        jwks_response = MagicMock()
        jwks_response.json.return_value = {"keys": [{"kty": "RSA", "kid": "test"}]}

        mock_requests.get.side_effect = [discovery_response, jwks_response]

        result = _get_oidc_jwks()

        assert mock_requests.get.call_count == 2
        mock_requests.get.assert_any_call("https://example.com/.well-known/openid_configuration", timeout=10, verify=True)
        mock_requests.get.assert_any_call("https://example.com/jwks", timeout=10, verify=True)
        assert result == {"keys": [{"kty": "RSA", "kid": "test"}]}

    @patch("mlflow_oidc_auth.auth.requests")
    @patch("mlflow_oidc_auth.auth.config")
    def test_get_oidc_jwks_uses_configured_timeout(self, mock_config, mock_requests):
        """Test that OIDC_HTTP_TIMEOUT_SECONDS overrides the default timeout"""
        mock_config.OIDC_DISCOVERY_URL = "https://example.com/.well-known/openid_configuration"
        mock_config.OIDC_HTTP_TIMEOUT_SECONDS = 3

        discovery_response = MagicMock()
        discovery_response.json.return_value = {"jwks_uri": "https://example.com/jwks"}
        jwks_response = MagicMock()
        jwks_response.json.return_value = {"keys": []}

        mock_requests.get.side_effect = [discovery_response, jwks_response]

        _get_oidc_jwks()

        for call in mock_requests.get.call_args_list:
            assert call.kwargs.get("timeout") == 3

    @patch("mlflow_oidc_auth.auth.requests")
    @patch("mlflow_oidc_auth.auth.config")
    def test_get_oidc_jwks_returns_cached(self, mock_config, mock_requests):
        """Test that second call returns cached JWKS without HTTP requests"""
        mock_config.OIDC_DISCOVERY_URL = "https://example.com/.well-known/openid_configuration"

        discovery_response = MagicMock()
        discovery_response.json.return_value = {"jwks_uri": "https://example.com/jwks"}
        jwks_response = MagicMock()
        jwks_response.json.return_value = {"keys": [{"kty": "RSA", "kid": "test"}]}

        mock_requests.get.side_effect = [discovery_response, jwks_response]

        # First call fetches from network
        result1 = _get_oidc_jwks()
        assert mock_requests.get.call_count == 2

        # Second call should return cached — no additional HTTP requests
        result2 = _get_oidc_jwks()
        assert mock_requests.get.call_count == 2  # Still 2, not 4
        assert result1 == result2

    @patch("mlflow_oidc_auth.auth.requests")
    @patch("mlflow_oidc_auth.auth.config")
    def test_get_oidc_jwks_force_refresh_bypasses_cache(self, mock_config, mock_requests):
        """Test that force_refresh=True fetches fresh JWKS"""
        mock_config.OIDC_DISCOVERY_URL = "https://example.com/.well-known/openid_configuration"

        discovery_response = MagicMock()
        discovery_response.json.return_value = {"jwks_uri": "https://example.com/jwks"}
        jwks_old = MagicMock()
        jwks_old.json.return_value = {"keys": [{"kty": "RSA", "kid": "old"}]}
        jwks_new = MagicMock()
        jwks_new.json.return_value = {"keys": [{"kty": "RSA", "kid": "new"}]}

        mock_requests.get.side_effect = [
            discovery_response,
            jwks_old,
            discovery_response,
            jwks_new,
        ]

        result1 = _get_oidc_jwks()
        assert result1 == {"keys": [{"kty": "RSA", "kid": "old"}]}

        result2 = _get_oidc_jwks(force_refresh=True)
        assert result2 == {"keys": [{"kty": "RSA", "kid": "new"}]}
        assert mock_requests.get.call_count == 4

    @patch("mlflow_oidc_auth.auth.config")
    def test_get_oidc_jwks_no_discovery_url(self, mock_config):
        """Test JWKS retrieval fails when OIDC_DISCOVERY_URL is not set"""
        mock_config.OIDC_DISCOVERY_URL = None

        with pytest.raises(ValueError, match="OIDC_DISCOVERY_URL is not set in the configuration"):
            _get_oidc_jwks()


class TestValidateToken:
    """Test validate_token with audience and caching integration.

    Since #313 the audience, issuer, keys and algorithms all come from the provider that issued
    the token, so each case installs a one-provider registry — the shape of every deployment
    that has not adopted a multi-provider configuration — instead of setting the flat variables
    directly. ``_jwt_for`` is patched because the decoder is now built per provider.
    """

    @staticmethod
    def _single_provider_registry(mock_config, audience=None, issuer=None):
        from mlflow_oidc_auth.provider_registry import ASYMMETRIC_ALGORITHMS, ProviderConfig, RegistryLoadResult

        provider = ProviderConfig(id="default", type="oidc", allowed_algorithms=ASYMMETRIC_ALGORITHMS, audience=audience, issuer=issuer)
        mock_config.AUTH_PROVIDERS = RegistryLoadResult(providers=[provider], errors=[], source="legacy")
        return provider

    @patch("mlflow_oidc_auth.auth.config")
    @patch("mlflow_oidc_auth.auth._get_oidc_jwks")
    @patch("mlflow_oidc_auth.auth._jwt_for")
    def test_validate_token_success(self, mock_jwt_for, mock_get_oidc_jwks, mock_config):
        """Test successful token validation without audience configured"""
        self._single_provider_registry(mock_config)
        mock_jwt_decode = mock_jwt_for.return_value.decode
        mock_jwks = {"keys": [{"kty": "RSA", "kid": "test"}]}
        mock_get_oidc_jwks.return_value = mock_jwks
        mock_payload = MagicMock()
        mock_jwt_decode.return_value = mock_payload

        result = validate_token("valid_token")

        mock_jwt_decode.assert_called_once_with("valid_token", mock_jwks, claims_options=None)
        mock_payload.validate.assert_called_once()
        assert result == mock_payload

    @patch("mlflow_oidc_auth.auth.config")
    @patch("mlflow_oidc_auth.auth._get_oidc_jwks")
    @patch("mlflow_oidc_auth.auth._jwt_for")
    def test_validate_token_with_audience(self, mock_jwt_for, mock_get_oidc_jwks, mock_config):
        """Test token validation passes audience claims_options when the provider pins one"""
        self._single_provider_registry(mock_config, audience="my-mlflow-app")
        mock_jwt_decode = mock_jwt_for.return_value.decode
        mock_jwks = {"keys": [{"kty": "RSA", "kid": "test"}]}
        mock_get_oidc_jwks.return_value = mock_jwks
        mock_payload = MagicMock()
        mock_jwt_decode.return_value = mock_payload

        result = validate_token("valid_token")

        expected_options = {"aud": {"essential": True, "value": "my-mlflow-app"}}
        mock_jwt_decode.assert_called_once_with("valid_token", mock_jwks, claims_options=expected_options)
        mock_payload.validate.assert_called_once()
        assert result == mock_payload

    @patch("mlflow_oidc_auth.auth.config")
    @patch("mlflow_oidc_auth.auth._get_oidc_jwks")
    @patch("mlflow_oidc_auth.auth._jwt_for")
    def test_validate_token_bad_signature_then_success(self, mock_jwt_for, mock_get_oidc_jwks, mock_config):
        """Test token validation with bad signature that succeeds after JWKS refresh"""
        self._single_provider_registry(mock_config)
        mock_jwt_decode = mock_jwt_for.return_value.decode
        mock_get_oidc_jwks.side_effect = [{"keys": "old_jwks"}, {"keys": "new_jwks"}]
        mock_payload = MagicMock()
        mock_jwt_decode.side_effect = [BadSignatureError("bad signature"), mock_payload]

        result = validate_token("token_with_new_key")

        assert result == mock_payload
        assert mock_get_oidc_jwks.call_count == 2
        # Second call uses force_refresh=True to handle key rotation. Both go through
        # _get_provider_jwks, which always passes the flag explicitly.
        mock_get_oidc_jwks.assert_any_call(force_refresh=False)
        mock_get_oidc_jwks.assert_any_call(force_refresh=True)

    @patch("mlflow_oidc_auth.auth.config")
    @patch("mlflow_oidc_auth.auth._get_oidc_jwks")
    @patch("mlflow_oidc_auth.auth._jwt_for")
    def test_validate_token_bad_signature_after_refresh(self, mock_jwt_for, mock_get_oidc_jwks, mock_config):
        """Test token validation that fails even after JWKS refresh"""
        self._single_provider_registry(mock_config)
        mock_jwt_decode = mock_jwt_for.return_value.decode
        mock_get_oidc_jwks.side_effect = [{"keys": "old_jwks"}, {"keys": "new_jwks"}]
        mock_jwt_decode.side_effect = [
            BadSignatureError("bad signature"),
            BadSignatureError("still bad"),
        ]

        with pytest.raises(BadSignatureError):
            validate_token("invalid_token")

        assert mock_get_oidc_jwks.call_count == 2

    @patch("mlflow_oidc_auth.auth.config")
    @patch("mlflow_oidc_auth.auth._get_oidc_jwks")
    @patch("mlflow_oidc_auth.auth._jwt_for")
    def test_validate_token_unexpected_error_after_refresh(self, mock_jwt_for, mock_get_oidc_jwks, mock_config):
        """Test token validation with unexpected error after JWKS refresh"""
        self._single_provider_registry(mock_config)
        mock_jwt_decode = mock_jwt_for.return_value.decode
        mock_get_oidc_jwks.side_effect = [{"keys": "old_jwks"}, {"keys": "new_jwks"}]
        mock_jwt_decode.side_effect = [
            BadSignatureError("bad signature"),
            ValueError("unexpected error"),
        ]

        with pytest.raises(ValueError, match="unexpected error"):
            validate_token("problematic_token")

        assert mock_get_oidc_jwks.call_count == 2

    @patch("mlflow_oidc_auth.auth.config")
    @patch("mlflow_oidc_auth.auth._get_oidc_jwks")
    @patch("mlflow_oidc_auth.auth._jwt_for")
    def test_validate_token_bad_signature_retry_with_audience(self, mock_jwt_for, mock_get_oidc_jwks, mock_config):
        """Test bad signature retry also passes audience claims_options"""
        self._single_provider_registry(mock_config, audience="my-mlflow-app")
        mock_jwt_decode = mock_jwt_for.return_value.decode
        mock_get_oidc_jwks.side_effect = [{"keys": "old_jwks"}, {"keys": "new_jwks"}]
        mock_payload = MagicMock()
        mock_jwt_decode.side_effect = [BadSignatureError("bad signature"), mock_payload]

        result = validate_token("token_with_new_key")

        assert result == mock_payload
        expected_options = {"aud": {"essential": True, "value": "my-mlflow-app"}}
        assert mock_jwt_decode.call_count == 2
        mock_jwt_decode.assert_any_call("token_with_new_key", {"keys": "old_jwks"}, claims_options=expected_options)
        mock_jwt_decode.assert_any_call("token_with_new_key", {"keys": "new_jwks"}, claims_options=expected_options)


class TestClaimsOptionsPerProvider:
    """``_claims_options_for`` replaces the flat ``_get_claims_options`` (#313).

    The constraints now come from the provider that issued the token rather than from one global
    pair of variables, because two issuers do not share an audience. For a single-provider
    deployment the values are the same ones: the synthesised ``default`` provider carries
    ``OIDC_AUDIENCE`` and ``OIDC_ISSUER``, which is what keeps the behaviour unchanged.
    """

    @staticmethod
    def _provider(**overrides):
        from mlflow_oidc_auth.provider_registry import ProviderConfig

        fields = {"id": "default", "type": "oidc"}
        fields.update(overrides)
        return ProviderConfig(**fields)

    def test_returns_none_when_neither_is_pinned(self):
        """The pre-#313 default for a deployment that set neither variable."""
        assert _claims_options_for(self._provider()) is None

    def test_returns_the_audience_when_pinned(self):
        options = _claims_options_for(self._provider(audience="my-mlflow-app"))

        assert options == {"aud": {"essential": True, "value": "my-mlflow-app"}}

    def test_returns_the_issuer_when_pinned(self):
        options = _claims_options_for(self._provider(issuer="https://idp.example.com"))

        assert options == {"iss": {"essential": True, "value": "https://idp.example.com"}}

    def test_returns_both(self):
        options = _claims_options_for(self._provider(audience="aud1", issuer="iss1"))

        assert options == {"aud": {"essential": True, "value": "aud1"}, "iss": {"essential": True, "value": "iss1"}}

    def test_two_providers_get_their_own_constraints(self):
        """The point of the change: one deployment, two issuers, two audiences."""
        entra = self._provider(id="entra", audience="mlflow-tracking", issuer="https://entra.invalid")
        cluster = self._provider(id="k8s", audience="mlflow-api", issuer="https://k8s.invalid")

        assert _claims_options_for(entra)["aud"]["value"] == "mlflow-tracking"
        assert _claims_options_for(cluster)["aud"]["value"] == "mlflow-api"

    def test_the_legacy_variables_still_reach_the_default_provider(self, monkeypatch):
        """The back-compat link. If this breaks, every existing deployment silently stops
        checking the audience it configured."""
        from mlflow_oidc_auth.provider_registry import build_provider_registry

        class FlatConfig:
            OIDC_DISCOVERY_URL = "https://idp.example.com/.well-known/openid-configuration"
            OIDC_CLIENT_ID = "client"
            OIDC_CLIENT_SECRET = "secret"  # not a credential: a stand-in for a config lookup
            OIDC_AUDIENCE = "legacy-audience"
            OIDC_ISSUER = "https://idp.example.com"
            OIDC_PROVIDER_DISPLAY_NAME = "Login with OIDC"

        class Manager:
            @staticmethod
            def get(key, default=None):
                return default

        registry = build_provider_registry(Manager(), FlatConfig())
        default = registry.by_id("default")

        assert default is not None
        assert _claims_options_for(default) == {
            "aud": {"essential": True, "value": "legacy-audience"},
            "iss": {"essential": True, "value": "https://idp.example.com"},
        }
