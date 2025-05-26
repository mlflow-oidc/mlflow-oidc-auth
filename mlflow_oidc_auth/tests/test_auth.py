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
        mlflow_oidc_app = importlib.import_module("mlflow_oidc_auth.app")
        mock_cache = MagicMock()
        mock_cache.get.return_value = None
        mock_app = MagicMock()
        mock_app.logger.debug = MagicMock()

        with patch.object(mlflow_oidc_app, "cache", mock_cache):
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

    @patch("mlflow_oidc_auth.auth._get_oidc_jwks")
    @patch("mlflow_oidc_auth.auth.jwt.decode")
    def test_validate_token_jwks_refresh_fails(self, mock_jwt_decode, mock_get_oidc_jwks):
        mock_get_oidc_jwks.side_effect = [Exception("fail1"), Exception("fail2")]
        mock_jwt_decode.side_effect = Exception("decode fail")
        mlflow_oidc_app = importlib.import_module("mlflow_oidc_auth.app")
        mock_mlflow_app = MagicMock()

        def warning(*args, **kwargs):
            pass

        def error(*args, **kwargs):
            pass

        mock_mlflow_app.logger.warning = warning
        mock_mlflow_app.logger.error = error
        with patch.object(mlflow_oidc_app, "app", mock_mlflow_app):
            with pytest.raises(Exception, match="fail1"):
                validate_token("mock_token")

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

    @patch("mlflow_oidc_auth.auth.store")
    def test_authenticate_request_basic_auth_missing_username_or_password(self, mock_store):
        # username is None
        mock_request = MagicMock()
        mock_request.authorization.username = None
        mock_request.authorization.password = "pw"
        with patch("mlflow_oidc_auth.auth.request", mock_request):
            assert authenticate_request_basic_auth() is False
        # password is None
        mock_request.authorization.username = "user"
        mock_request.authorization.password = None
        with patch("mlflow_oidc_auth.auth.request", mock_request):
            assert authenticate_request_basic_auth() is False

    def test_authenticate_request_basic_auth_empty(self):
        # Both username and password are None
        mock_request = MagicMock()
        mock_request.authorization.username = None
        mock_request.authorization.password = None
        with patch("mlflow_oidc_auth.auth.request", mock_request):
            assert authenticate_request_basic_auth() is False

    @patch("mlflow_oidc_auth.auth.validate_token")
    def test_authenticate_request_bearer_token_invalid(self, mock_validate_token):
        # validate_token raises Exception
        mock_request = MagicMock()
        mock_request.authorization.token = "bad"
        mock_validate_token.side_effect = Exception("fail")
        with patch("mlflow_oidc_auth.auth.request", mock_request):
            assert authenticate_request_bearer_token() is False

    def test_authenticate_request_bearer_token_empty(self):
        # No authorization
        mock_request = MagicMock()
        mock_request.authorization = None
        with patch("mlflow_oidc_auth.auth.request", mock_request):
            assert authenticate_request_bearer_token() is False
        # Authorization but no token
        mock_request.authorization = MagicMock()
        mock_request.authorization.token = None
        with patch("mlflow_oidc_auth.auth.request", mock_request):
            assert authenticate_request_bearer_token() is False

    def test_handle_token_validation_success(self):
        # Simulate successful token validation
        oauth_instance = MagicMock()
        token = {"access_token": "tok"}
        oauth_instance.oidc.authorize_access_token.return_value = token
        from mlflow_oidc_auth.auth import handle_token_validation

        assert handle_token_validation(oauth_instance) == token

    def test_handle_token_validation_bad_signature(self):
        # Simulate BadSignatureError and then success
        oauth_instance = MagicMock()
        from authlib.jose.errors import BadSignatureError

        oauth_instance.oidc.authorize_access_token.side_effect = [BadSignatureError(result=None), {"access_token": "tok"}]
        oauth_instance.oidc.load_server_metadata = MagicMock()
        mlflow_oidc_app = importlib.import_module("mlflow_oidc_auth.app")
        mock_mlflow_app = MagicMock()
        mock_mlflow_app.logger.warning = lambda *a, **k: None
        mock_mlflow_app.logger.error = lambda *a, **k: None
        with patch.object(mlflow_oidc_app, "app", mock_mlflow_app):
            from mlflow_oidc_auth.auth import handle_token_validation

            assert handle_token_validation(oauth_instance) == {"access_token": "tok"}
        # logger.warning is called, but we do not assert call count here due to direct function replacement

    def test_handle_token_validation_bad_signature_fails(self):
        # Simulate BadSignatureError twice
        oauth_instance = MagicMock()
        from authlib.jose.errors import BadSignatureError

        oauth_instance.oidc.authorize_access_token.side_effect = [
            BadSignatureError(result=None),
            BadSignatureError(result=None),
        ]
        oauth_instance.oidc.load_server_metadata = MagicMock()
        mlflow_oidc_app = importlib.import_module("mlflow_oidc_auth.app")
        mock_mlflow_app = MagicMock()
        mock_mlflow_app.logger.warning = lambda *a, **k: None
        mock_mlflow_app.logger.error = lambda *a, **k: None
        with patch.object(mlflow_oidc_app, "app", mock_mlflow_app):
            from mlflow_oidc_auth.auth import handle_token_validation

            assert handle_token_validation(oauth_instance) is None
        # logger.error is called, but we do not assert call count here due to direct function replacement

    def test_handle_user_and_group_management_admin(self):
        # User is admin
        token = {
            "userinfo": {"email": "admin@example.com", "name": "Admin", "groups": ["admin", "users"]},
            "access_token": "tok",
        }
        from mlflow_oidc_auth.auth import handle_user_and_group_management

        config = importlib.import_module("mlflow_oidc_auth.config").config
        config.OIDC_GROUP_DETECTION_PLUGIN = None
        config.OIDC_GROUPS_ATTRIBUTE = "groups"
        config.OIDC_ADMIN_GROUP_NAME = "admin"
        config.OIDC_GROUP_NAME = ["users"]
        with patch("mlflow_oidc_auth.auth.create_user") as mock_create_user, patch(
            "mlflow_oidc_auth.auth.populate_groups"
        ) as mock_populate_groups, patch("mlflow_oidc_auth.auth.update_user") as mock_update_user, patch(
            "mlflow_oidc_auth.auth.app"
        ) as mock_app:
            mock_app.logger.debug = MagicMock()
            handle_user_and_group_management(token)
            mock_create_user.assert_called_once()
            mock_populate_groups.assert_called_once()
            mock_update_user.assert_called_once()

    def test_handle_user_and_group_management_denied(self):
        # User is not admin and not in allowed group
        token = {"userinfo": {"email": "user@example.com", "name": "User", "groups": ["guests"]}, "access_token": "tok"}
        from mlflow_oidc_auth.auth import handle_user_and_group_management

        config = importlib.import_module("mlflow_oidc_auth.config").config
        config.OIDC_GROUP_DETECTION_PLUGIN = None
        config.OIDC_GROUPS_ATTRIBUTE = "groups"
        config.OIDC_ADMIN_GROUP_NAME = "admin"
        config.OIDC_GROUP_NAME = ["users"]
        with patch("mlflow_oidc_auth.auth.app") as mock_app:
            mock_app.logger.debug = MagicMock()
            errors = handle_user_and_group_management(token)
            assert "Authorization error: User is not allowed to login." in errors

    def test_handle_user_and_group_management_missing_email_and_name(self):
        # Missing email and display name
        token = {"userinfo": {}, "access_token": "tok"}
        from mlflow_oidc_auth.auth import handle_user_and_group_management

        config = importlib.import_module("mlflow_oidc_auth.config").config
        config.OIDC_GROUP_DETECTION_PLUGIN = None
        config.OIDC_GROUPS_ATTRIBUTE = "groups"
        config.OIDC_ADMIN_GROUP_NAME = "admin"
        config.OIDC_GROUP_NAME = ["users"]
        errors = handle_user_and_group_management(token)
        assert "User profile error: No email provided in OIDC userinfo." in errors
        assert "User profile error: No display name provided in OIDC userinfo." in errors

    def test_handle_user_and_group_management_group_plugin_exception(self):
        # Plugin raises exception
        token = {"userinfo": {"email": "user@example.com", "name": "User"}, "access_token": "tok"}
        from mlflow_oidc_auth.auth import handle_user_and_group_management

        config = importlib.import_module("mlflow_oidc_auth.config").config
        config.OIDC_GROUP_DETECTION_PLUGIN = "mlflow_oidc_auth.tests.test_auth"
        config.OIDC_ADMIN_GROUP_NAME = "admin"
        config.OIDC_GROUP_NAME = ["users"]

        # Provide a fake plugin that raises
        def get_user_groups(token):
            raise Exception("fail")

        import sys

        sys.modules["mlflow_oidc_auth.tests.test_auth"] = MagicMock(get_user_groups=get_user_groups)
        errors = handle_user_and_group_management(token)
        assert "Group detection error: Failed to get user groups" in errors

    def test_handle_user_and_group_management_db_exception(self):
        # DB update fails
        token = {
            "userinfo": {"email": "admin@example.com", "name": "Admin", "groups": ["admin", "users"]},
            "access_token": "tok",
        }
        from mlflow_oidc_auth.auth import handle_user_and_group_management

        config = importlib.import_module("mlflow_oidc_auth.config").config
        config.OIDC_GROUP_DETECTION_PLUGIN = None
        config.OIDC_GROUPS_ATTRIBUTE = "groups"
        config.OIDC_ADMIN_GROUP_NAME = "admin"
        config.OIDC_GROUP_NAME = ["users"]
        with patch("mlflow_oidc_auth.auth.create_user", side_effect=Exception("fail")), patch(
            "mlflow_oidc_auth.auth.populate_groups"
        ), patch("mlflow_oidc_auth.auth.update_user"), patch("mlflow_oidc_auth.auth.app"):
            errors = handle_user_and_group_management(token)
            assert "User/group DB error: Failed to update user/groups" in errors
