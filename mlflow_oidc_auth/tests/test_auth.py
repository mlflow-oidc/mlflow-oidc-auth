import importlib
from unittest.mock import MagicMock, patch

import pytest

from mlflow_oidc_auth.auth import (
    _get_oidc_jwks,
    authenticate_request_basic_auth,
    authenticate_request_bearer_token,
    get_oauth_instance,
    validate_token,
)


class TestAuth:
    @patch("mlflow_oidc_auth.auth.OAuth")
    @patch("mlflow_oidc_auth.auth.config")
    def test_get_oauth_instance(self, mock_config, mock_oauth):
        mock_app = MagicMock()
        mock_oauth_instance = MagicMock()
        mock_oauth.return_value = mock_oauth_instance

        mock_config.OIDC_CLIENT_ID = "mock_client_id"
        mock_config.OIDC_CLIENT_SECRET = "mock_client_secret"
        mock_config.OIDC_DISCOVERY_URL = "mock_discovery_url"
        mock_config.OIDC_SCOPE = "mock_scope"

        result = get_oauth_instance(mock_app)

        mock_oauth.assert_called_once_with(mock_app)
        mock_oauth_instance.register.assert_called_once_with(
            name="oidc",
            client_id="mock_client_id",
            client_secret="mock_client_secret",
            server_metadata_url="mock_discovery_url",
            client_kwargs={"scope": "mock_scope"},
        )
        assert result == mock_oauth_instance

    @patch("mlflow_oidc_auth.auth.requests")
    @patch("mlflow_oidc_auth.auth.config")
    def test__get_oidc_jwks(self, mock_config, mock_requests):
        mock_cache = MagicMock()
        mock_app = MagicMock()
        mock_app.logger.debug = MagicMock()
        mock_requests.get.return_value.json.return_value = {"jwks_uri": "mock_jwks_uri"}
        mock_cache.get.return_value = None
        mock_config.OIDC_DISCOVERY_URL = "mock_discovery_url"

        # cache and app are imported within the _get_oidc_jwks function
        mlflow_oidc_app = importlib.import_module("mlflow_oidc_auth.app")
        with patch.object(mlflow_oidc_app, "cache", mock_cache):
            with patch.object(mlflow_oidc_app, "app", mock_app):
                result = _get_oidc_jwks()

                assert len(mock_requests.get.call_args) == 2

                assert mock_requests.get.call_args[0][0] == "mock_jwks_uri"
                assert mock_requests.get.call_args[1] == {}  # TODO: proper patch for first .get() return_value

                mock_cache.set.assert_called_once_with("jwks", mock_requests.get.return_value.json.return_value, timeout=3600)
                assert result == mock_requests.get.return_value.json.return_value

    @patch("mlflow_oidc_auth.auth.app")
    def test__get_oidc_jwks_cache_hit(self, mock_app):
        mock_cache = MagicMock()
        mock_cache.get.return_value = {"keys": "mock_keys"}
        mock_app.logger.debug = MagicMock()
        mlflow_oidc_app = importlib.import_module("mlflow_oidc_auth.app")
        with patch.object(mlflow_oidc_app, "cache", mock_cache):
            result = _get_oidc_jwks()
            mock_app.logger.debug.assert_called_once_with("JWKS cache hit")
            assert result == {"keys": "mock_keys"}

    @patch("mlflow_oidc_auth.auth.config")
    def test__get_oidc_jwks_no_discovery_url(self, mock_config):
        mock_config.OIDC_DISCOVERY_URL = None
        with pytest.raises(ValueError, match="OIDC_DISCOVERY_URL is not set in the configuration"):
            _get_oidc_jwks()

    @patch("mlflow_oidc_auth.auth._get_oidc_jwks")
    @patch("mlflow_oidc_auth.auth.jwt.decode")
    def test_validate_token(self, mock_jwt_decode, mock_get_oidc_jwks):
        mock_jwks = {"keys": "mock_keys"}
        mock_get_oidc_jwks.return_value = mock_jwks
        mock_payload = MagicMock()
        mock_jwt_decode.return_value = mock_payload

        token = "mock_token"
        result = validate_token(token)

        mock_get_oidc_jwks.assert_called_once()
        mock_jwt_decode.assert_called_once_with(token, mock_jwks)
        mock_payload.validate.assert_called_once()
        assert result == mock_payload

    @patch("mlflow_oidc_auth.auth.store")
    def test_authenticate_request_basic_auth_uses_authenticate_user(self, mock_store):
        mock_request = MagicMock()
        mock_request.authorization.username = "mock_username"
        mock_request.authorization.password = "mock_password"
        mock_store.authenticate_user.return_value = True

        with patch("mlflow_oidc_auth.auth.request", mock_request):
            # for some reason decorator doesn't mock flask
            result = authenticate_request_basic_auth()

            mock_store.authenticate_user.assert_called_once_with("mock_username", "mock_password")
            assert result == True

    def test_authenticate_request_basic_auth_no_authorization(self):
        mock_request = MagicMock()
        mock_request.authorization = None
        with patch("mlflow_oidc_auth.auth.request", mock_request):
            result = authenticate_request_basic_auth()
            assert result == False

    @patch("mlflow_oidc_auth.auth.store")
    @patch("mlflow_oidc_auth.auth.app")
    def test_authenticate_request_basic_auth_user_not_authenticated(self, mock_app, mock_store):
        mock_request = MagicMock()
        mock_request.authorization.username = "mock_username"
        mock_request.authorization.password = "mock_password"
        mock_store.authenticate_user.return_value = False
        mock_app.logger.debug = MagicMock()

        with patch("mlflow_oidc_auth.auth.request", mock_request):
            result = authenticate_request_basic_auth()
            mock_app.logger.debug.assert_called_with("User %s not authenticated", "mock_username")
            assert result == False

    @patch("mlflow_oidc_auth.auth.validate_token")
    def test_authenticate_request_bearer_token_uses_validate_token(self, mock_validate_token):
        mock_request = MagicMock()
        mock_request.authorization.token = "mock_token"
        mock_validate_token.return_value = MagicMock()
        with patch("mlflow_oidc_auth.auth.request", mock_request):
            # for some reason decorator doesn't mock flask
            result = authenticate_request_bearer_token()

            mock_validate_token.assert_called_once_with("mock_token")
            assert result == True

    @patch("mlflow_oidc_auth.auth.validate_token")
    def test_authenticate_request_bearer_token_exception_returns_false(self, mock_validate_token):
        mock_request = MagicMock()
        mock_request.authorization.token = "mock_token"
        mock_validate_token.side_effect = Exception()
        with patch("mlflow_oidc_auth.auth.request", mock_request):
            # for some reason decorator doesn't mock flask
            result = authenticate_request_bearer_token()

            mock_validate_token.assert_called_once_with("mock_token")
            assert result == False

    def test_authenticate_request_bearer_token_no_authorization(self):
        mock_request = MagicMock()
        mock_request.authorization = None
        with patch("mlflow_oidc_auth.auth.request", mock_request):
            result = authenticate_request_bearer_token()
            assert result == False

    def test_authenticate_request_bearer_token_no_token(self):
        mock_request = MagicMock()
        mock_request.authorization.token = None
        with patch("mlflow_oidc_auth.auth.request", mock_request):
            result = authenticate_request_bearer_token()
            assert result == False
