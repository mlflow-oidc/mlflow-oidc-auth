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

        mock_config.OIDC_CLIENT_ID = "client_id"
        mock_config.OIDC_CLIENT_SECRET = "client_secret"
        mock_config.OIDC_DISCOVERY_URL = "discovery_url"
        mock_config.OIDC_SCOPE = "scope"

        result = get_oauth_instance(mock_app)

        mock_oauth.assert_called_once_with(mock_app)
        mock_oauth_instance.register.assert_called_once_with(
            name="oidc",
            client_id="client_id",
            client_secret="client_secret",
            server_metadata_url="discovery_url",
            client_kwargs={"scope": "scope"},
        )
        assert result == mock_oauth_instance

    @patch("mlflow_oidc_auth.auth.requests")
    @patch("mlflow_oidc_auth.auth.config")
    def test_get_oidc_jwks_success(self, mock_config, mock_requests):
        mock_cache = MagicMock()
        mock_app = MagicMock()
        mock_requests.get.return_value.json.return_value = {"jwks_uri": "jwks_uri"}
        mock_cache.get.return_value = None
        mock_config.OIDC_DISCOVERY_URL = "discovery_url"

        mlflow_oidc_app = importlib.import_module("mlflow_oidc_auth.app")
        with patch.object(mlflow_oidc_app, "cache", mock_cache), patch.object(mlflow_oidc_app, "app", mock_app):
            result = _get_oidc_jwks()
            mock_cache.set.assert_called_once_with("jwks", mock_requests.get.return_value.json.return_value, timeout=3600)
            assert result == mock_requests.get.return_value.json.return_value

    @patch("mlflow_oidc_auth.auth.app")
    def test_get_oidc_jwks_cache_hit(self, mock_app):
        mock_cache = MagicMock()
        mock_cache.get.return_value = {"keys": "cached_keys"}

        mlflow_oidc_app = importlib.import_module("mlflow_oidc_auth.app")
        with patch.object(mlflow_oidc_app, "cache", mock_cache):
            result = _get_oidc_jwks()
            assert result == {"keys": "cached_keys"}

    @patch("mlflow_oidc_auth.auth.config")
    def test_get_oidc_jwks_no_discovery_url(self, mock_config):
        mock_config.OIDC_DISCOVERY_URL = None
        mlflow_oidc_app = importlib.import_module("mlflow_oidc_auth.app")
        mock_cache = MagicMock()
        mock_cache.get.return_value = None

        with patch.object(mlflow_oidc_app, "cache", mock_cache):
            with pytest.raises(ValueError, match="OIDC_DISCOVERY_URL is not set"):
                _get_oidc_jwks()

    @patch("mlflow_oidc_auth.auth.config")
    def test_get_oidc_jwks_clear_cache(self, mock_config):
        mock_cache = MagicMock()
        mock_app = MagicMock()
        mock_config.OIDC_DISCOVERY_URL = "discovery_url"

        mlflow_oidc_app = importlib.import_module("mlflow_oidc_auth.app")
        with patch.object(mlflow_oidc_app, "cache", mock_cache), patch.object(mlflow_oidc_app, "app", mock_app):
            with patch("mlflow_oidc_auth.auth.requests") as mock_requests:
                mock_requests.get.return_value.json.return_value = {"jwks_uri": "jwks_uri"}
                mock_cache.get.return_value = None

                _get_oidc_jwks(clear_cache=True)
                mock_cache.delete.assert_called_once_with("jwks")

    @patch("mlflow_oidc_auth.auth._get_oidc_jwks")
    @patch("mlflow_oidc_auth.auth.jwt.decode")
    def test_validate_token_success(self, mock_jwt_decode, mock_get_oidc_jwks):
        mock_jwks = {"keys": "jwks"}
        mock_get_oidc_jwks.return_value = mock_jwks
        mock_payload = MagicMock()
        mock_jwt_decode.return_value = mock_payload

        result = validate_token("token")

        mock_jwt_decode.assert_called_once_with("token", mock_jwks)
        mock_payload.validate.assert_called_once()
        assert result == mock_payload

    @patch("mlflow_oidc_auth.auth._get_oidc_jwks")
    @patch("mlflow_oidc_auth.auth.jwt.decode")
    def test_validate_token_bad_signature_then_success(self, mock_jwt_decode, mock_get_oidc_jwks):
        from authlib.jose.errors import BadSignatureError

        mock_get_oidc_jwks.side_effect = [{"keys": "jwks1"}, {"keys": "jwks2"}]
        mock_payload = MagicMock()
        mock_jwt_decode.side_effect = [BadSignatureError("bad sig"), mock_payload]

        mlflow_oidc_app = importlib.import_module("mlflow_oidc_auth.app")
        with patch.object(mlflow_oidc_app, "app", MagicMock()):
            result = validate_token("token")
            assert result == mock_payload
            assert mock_get_oidc_jwks.call_count == 2

    @patch("mlflow_oidc_auth.auth._get_oidc_jwks")
    @patch("mlflow_oidc_auth.auth.jwt.decode")
    def test_validate_token_exception_after_refresh(self, mock_jwt_decode, mock_get_oidc_jwks):
        from authlib.jose.errors import BadSignatureError

        mock_get_oidc_jwks.side_effect = [{"keys": "jwks1"}, {"keys": "jwks2"}]
        mock_jwt_decode.side_effect = [BadSignatureError("bad sig"), Exception("other error")]

        mlflow_oidc_app = importlib.import_module("mlflow_oidc_auth.app")
        with patch.object(mlflow_oidc_app, "app", MagicMock()):
            with pytest.raises(Exception, match="other error"):
                validate_token("token")
            assert mock_get_oidc_jwks.call_count == 2

    @patch("mlflow_oidc_auth.auth.store")
    def test_authenticate_request_basic_auth_success(self, mock_store):
        mock_request = MagicMock()
        mock_request.authorization.username = "user"
        mock_request.authorization.password = "pass"
        mock_store.authenticate_user.return_value = True

        with patch("mlflow_oidc_auth.auth.request", mock_request):
            result = authenticate_request_basic_auth()
            mock_store.authenticate_user.assert_called_once_with("user", "pass")
            assert result is True

    def test_authenticate_request_basic_auth_no_auth(self):
        mock_request = MagicMock()
        mock_request.authorization = None

        with patch("mlflow_oidc_auth.auth.request", mock_request):
            assert authenticate_request_basic_auth() is False

    @patch("mlflow_oidc_auth.auth.store")
    def test_authenticate_request_basic_auth_invalid_credentials(self, mock_store):
        mock_request = MagicMock()
        mock_request.authorization.username = "user"
        mock_request.authorization.password = "wrong"
        mock_store.authenticate_user.return_value = False

        with patch("mlflow_oidc_auth.auth.request", mock_request), patch("mlflow_oidc_auth.auth.app"):
            assert authenticate_request_basic_auth() is False

    @patch("mlflow_oidc_auth.auth.validate_token")
    def test_authenticate_request_bearer_token_success(self, mock_validate_token):
        mock_request = MagicMock()
        mock_request.authorization.token = "token"
        mock_validate_token.return_value = {"email": "user@example.com"}

        with patch("mlflow_oidc_auth.auth.request", mock_request), patch("mlflow_oidc_auth.auth.app"):
            result = authenticate_request_bearer_token()
            mock_validate_token.assert_called_once_with("token")
            assert result is True

    def test_authenticate_request_bearer_token_no_auth(self):
        mock_request = MagicMock()
        mock_request.authorization = None

        with patch("mlflow_oidc_auth.auth.request", mock_request), patch("mlflow_oidc_auth.auth.app"):
            assert authenticate_request_bearer_token() is False

    @patch("mlflow_oidc_auth.auth.validate_token")
    def test_authenticate_request_bearer_token_invalid(self, mock_validate_token):
        mock_request = MagicMock()
        mock_request.authorization.token = "invalid"
        mock_validate_token.side_effect = Exception("Invalid token")

        with patch("mlflow_oidc_auth.auth.request", mock_request), patch("mlflow_oidc_auth.auth.app"):
            assert authenticate_request_bearer_token() is False

    def test_handle_token_validation_success(self):
        from mlflow_oidc_auth.auth import handle_token_validation

        oauth_instance = MagicMock()
        token = {"access_token": "token"}
        oauth_instance.oidc.authorize_access_token.return_value = token

        with patch("mlflow_oidc_auth.auth.app"):
            result = handle_token_validation(oauth_instance)
            assert result == token

    def test_handle_token_validation_bad_signature_recovery(self):
        from mlflow_oidc_auth.auth import handle_token_validation
        from authlib.jose.errors import BadSignatureError

        oauth_instance = MagicMock()
        oauth_instance.oidc.authorize_access_token.side_effect = [BadSignatureError(result=None), {"access_token": "token"}]

        mlflow_oidc_app = importlib.import_module("mlflow_oidc_auth.app")
        with patch.object(mlflow_oidc_app, "app", MagicMock()):
            result = handle_token_validation(oauth_instance)
            assert result == {"access_token": "token"}

    def test_handle_token_validation_bad_signature_fails(self):
        from mlflow_oidc_auth.auth import handle_token_validation
        from authlib.jose.errors import BadSignatureError

        oauth_instance = MagicMock()
        oauth_instance.oidc.authorize_access_token.side_effect = [
            BadSignatureError(result=None),
            BadSignatureError(result=None),
        ]

        with patch("mlflow_oidc_auth.auth.app", MagicMock()):
            result = handle_token_validation(oauth_instance)
            assert result is None

    def test_handle_user_and_group_management_success(self):
        from mlflow_oidc_auth.auth import handle_user_and_group_management

        token = {
            "userinfo": {"email": "admin@example.com", "name": "Admin", "groups": ["admin"]},
            "access_token": "token",
        }

        config = importlib.import_module("mlflow_oidc_auth.config").config
        config.OIDC_GROUP_DETECTION_PLUGIN = None
        config.OIDC_GROUPS_ATTRIBUTE = "groups"
        config.OIDC_ADMIN_GROUP_NAME = "admin"
        config.OIDC_GROUP_NAME = ["users"]

        with patch("mlflow_oidc_auth.auth.create_user") as mock_create, patch("mlflow_oidc_auth.auth.populate_groups") as mock_populate, patch(
            "mlflow_oidc_auth.auth.update_user"
        ) as mock_update, patch("mlflow_oidc_auth.auth.app"):
            errors = handle_user_and_group_management(token)
            assert errors == []
            mock_create.assert_called_once()
            mock_populate.assert_called_once()
            mock_update.assert_called_once()

    def test_handle_user_and_group_management_missing_profile(self):
        from mlflow_oidc_auth.auth import handle_user_and_group_management

        token = {"userinfo": {}, "access_token": "token"}
        errors = handle_user_and_group_management(token)
        assert "No email provided" in str(errors)
        assert "No display name provided" in str(errors)

    def test_handle_userinfo_missing_field_email_but_has_preferred_username_success(self):
        from mlflow_oidc_auth.auth import handle_user_and_group_management

        token = {"userinfo": {"name": "Test Tes", "preferred_username": "techaccount@example.net", "groups": ["users"]}, "access_token": "token"}
        config = importlib.import_module("mlflow_oidc_auth.config").config
        config.OIDC_GROUP_DETECTION_PLUGIN = None
        config.OIDC_GROUPS_ATTRIBUTE = "groups"
        config.OIDC_ADMIN_GROUP_NAME = "admin"
        config.OIDC_GROUP_NAME = ["users"]

        with patch("mlflow_oidc_auth.auth.create_user") as mock_create, patch("mlflow_oidc_auth.auth.populate_groups") as mock_populate, patch(
            "mlflow_oidc_auth.auth.update_user"
        ) as mock_update, patch("mlflow_oidc_auth.auth.app"):
            errors = handle_user_and_group_management(token)
            assert errors == []
            mock_create.assert_called_once()
            mock_populate.assert_called_once()
            mock_update.assert_called_once()

    def test_handle_user_and_group_management_unauthorized(self):
        from mlflow_oidc_auth.auth import handle_user_and_group_management

        token = {"userinfo": {"email": "user@example.com", "name": "User", "groups": ["guests"]}}

        config = importlib.import_module("mlflow_oidc_auth.config").config
        config.OIDC_GROUP_DETECTION_PLUGIN = None
        config.OIDC_GROUPS_ATTRIBUTE = "groups"
        config.OIDC_ADMIN_GROUP_NAME = "admin"
        config.OIDC_GROUP_NAME = ["users"]

        with patch("mlflow_oidc_auth.auth.app"):
            errors = handle_user_and_group_management(token)
            assert "not allowed to login" in str(errors)

    def test_handle_user_and_group_management_group_plugin_error(self):
        from mlflow_oidc_auth.auth import handle_user_and_group_management

        token = {
            "userinfo": {"email": "user@example.com", "name": "User"},
            "access_token": "token",
        }

        config = importlib.import_module("mlflow_oidc_auth.config").config
        config.OIDC_GROUP_DETECTION_PLUGIN = "nonexistent.module"

        with patch("mlflow_oidc_auth.auth.app"):
            errors = handle_user_and_group_management(token)
            assert "Group detection error: Failed to get user groups" in errors

    def test_handle_user_and_group_management_group_missing_error(self):
        from mlflow_oidc_auth.auth import handle_user_and_group_management

        token = {
            "userinfo": {"email": "user@example.com", "name": "User"},
            "access_token": "token",
        }

        config = importlib.import_module("mlflow_oidc_auth.config").config
        config.OIDC_GROUP_DETECTION_PLUGIN = None
        config.OIDC_GROUPS_ATTRIBUTE = "groups"

        with patch("mlflow_oidc_auth.auth.app"):
            errors = handle_user_and_group_management(token)
            assert "Group detection error: Failed to get user groups" in errors

    def test_handle_user_and_group_management_db_error(self):
        from mlflow_oidc_auth.auth import handle_user_and_group_management

        token = {
            "userinfo": {"email": "admin@example.com", "name": "Admin", "groups": ["admin"]},
            "access_token": "token",
        }

        config = importlib.import_module("mlflow_oidc_auth.config").config
        config.OIDC_GROUP_DETECTION_PLUGIN = None
        config.OIDC_GROUPS_ATTRIBUTE = "groups"
        config.OIDC_ADMIN_GROUP_NAME = "admin"
        config.OIDC_GROUP_NAME = ["users"]

        with patch("mlflow_oidc_auth.auth.create_user", side_effect=Exception("DB error")), patch("mlflow_oidc_auth.auth.populate_groups"), patch(
            "mlflow_oidc_auth.auth.update_user"
        ), patch("mlflow_oidc_auth.auth.app"):
            errors = handle_user_and_group_management(token)
            assert "User/group DB error: Failed to update user/groups" in errors

    def test_process_oidc_callback_success(self):
        from mlflow_oidc_auth.auth import process_oidc_callback

        mock_request = MagicMock()
        mock_request.args.get.side_effect = lambda k: "state_value" if k == "state" else None
        session = {"oauth_state": "state_value"}
        token = {"userinfo": {"email": "user@example.com"}}

        with patch("mlflow_oidc_auth.auth.get_oauth_instance") as mock_oauth, patch("mlflow_oidc_auth.auth.handle_token_validation", return_value=token), patch(
            "mlflow_oidc_auth.auth.handle_user_and_group_management", return_value=[]
        ), patch("mlflow_oidc_auth.auth.app"):
            mock_oauth.return_value.oidc = MagicMock()
            email, errors = process_oidc_callback(mock_request, session)
            assert email == "user@example.com"
            assert errors == []

    def test_process_oidc_callback_oidc_error(self):
        from mlflow_oidc_auth.auth import process_oidc_callback

        mock_request = MagicMock()
        mock_request.args.get.side_effect = lambda k: "error" if k == "error" else "description"

        email, errors = process_oidc_callback(mock_request, {})
        assert email is None
        assert "OIDC provider error" in str(errors)

    def test_process_oidc_callback_state_mismatch(self):
        from mlflow_oidc_auth.auth import process_oidc_callback

        mock_request = MagicMock()
        mock_request.args.get.side_effect = lambda k: "wrong_state" if k == "state" else None
        session = {"oauth_state": "correct_state"}

        email, errors = process_oidc_callback(mock_request, session)
        assert email is None
        assert "Invalid state parameter" in str(errors)

    def test_process_oidc_callback_missing_oauth_state(self):
        from mlflow_oidc_auth.auth import process_oidc_callback

        mock_request = MagicMock()
        mock_request.args.get.side_effect = lambda k: "state_value" if k == "state" else None
        session = {}  # Missing oauth_state

        email, errors = process_oidc_callback(mock_request, session)
        assert email is None
        assert "Missing OAuth state in session" in str(errors)

    def test_process_oidc_callback_oauth_instance_none(self):
        from mlflow_oidc_auth.auth import process_oidc_callback

        mock_request = MagicMock()
        mock_request.args.get.side_effect = lambda k: "state_value" if k == "state" else None
        session = {"oauth_state": "state_value"}

        with patch("mlflow_oidc_auth.auth.get_oauth_instance", return_value=None), patch("mlflow_oidc_auth.auth.app"):
            email, errors = process_oidc_callback(mock_request, session)
            assert email is None
            assert "OAuth instance or OIDC is not properly initialized" in str(errors)

    def test_process_oidc_callback_oauth_instance_no_oidc(self):
        from mlflow_oidc_auth.auth import process_oidc_callback

        mock_request = MagicMock()
        mock_request.args.get.side_effect = lambda k: "state_value" if k == "state" else None
        session = {"oauth_state": "state_value"}

        class DummyOAuth:
            pass  # No oidc attribute

        with patch("mlflow_oidc_auth.auth.get_oauth_instance", return_value=DummyOAuth()), patch("mlflow_oidc_auth.auth.app"):
            email, errors = process_oidc_callback(mock_request, session)
            assert email is None
            assert "OAuth instance or OIDC is not properly initialized" in str(errors)

    def test_process_oidc_callback_token_validation_none(self):
        from mlflow_oidc_auth.auth import process_oidc_callback

        mock_request = MagicMock()
        mock_request.args.get.side_effect = lambda k: "state_value" if k == "state" else None
        session = {"oauth_state": "state_value"}

        with patch("mlflow_oidc_auth.auth.get_oauth_instance") as mock_oauth, patch("mlflow_oidc_auth.auth.handle_token_validation", return_value=None), patch(
            "mlflow_oidc_auth.auth.app"
        ):
            mock_oauth.return_value.oidc = MagicMock()
            email, errors = process_oidc_callback(mock_request, session)
            assert email is None
            assert "Invalid token signature or token could not be validated" in str(errors)

    def test_process_oidc_callback_user_management_errors(self):
        from mlflow_oidc_auth.auth import process_oidc_callback

        mock_request = MagicMock()
        mock_request.args.get.side_effect = lambda k: "state_value" if k == "state" else None
        session = {"oauth_state": "state_value"}
        token = {"userinfo": {"email": "user@example.com"}}

        with patch("mlflow_oidc_auth.auth.get_oauth_instance") as mock_oauth, patch("mlflow_oidc_auth.auth.handle_token_validation", return_value=token), patch(
            "mlflow_oidc_auth.auth.handle_user_and_group_management", return_value=["Some error"]
        ), patch("mlflow_oidc_auth.auth.app"):
            mock_oauth.return_value.oidc = MagicMock()
            email, errors = process_oidc_callback(mock_request, session)
            assert email is None
            assert "Some error" in errors
