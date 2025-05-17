import unittest
from unittest.mock import MagicMock, patch

from flask import Flask
from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import BAD_REQUEST, INVALID_PARAMETER_VALUE, RESOURCE_DOES_NOT_EXIST

from mlflow_oidc_auth.permissions import Permission
from mlflow_oidc_auth.utils import (
    PermissionResult,
    can_manage_experiment,
    can_manage_registered_model,
    check_experiment_permission,
    check_prompt_permission,
    check_registered_model_permission,
    get_is_admin,
    get_permission_from_store_or_default,
)


class TestUtils(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config["TESTING"] = True
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()

    def tearDown(self):
        self.app_context.pop()

    @patch("mlflow_oidc_auth.utils.store")
    @patch("mlflow_oidc_auth.utils.get_username")
    def test_get_is_admin(self, mock_get_username, mock_store):
        with self.app.test_request_context():
            mock_get_username.return_value = "user"
            mock_store.get_user.return_value.is_admin = True
            self.assertTrue(get_is_admin())
            mock_store.get_user.return_value.is_admin = False
            self.assertFalse(get_is_admin())

    @patch("mlflow_oidc_auth.utils.store")
    @patch("mlflow_oidc_auth.utils.config")
    @patch("mlflow_oidc_auth.utils.get_permission")
    def test_get_permission_from_store_or_default(self, mock_get_permission, mock_config, mock_store):
        with self.app.test_request_context():
            mock_store_permission_user_func = MagicMock()
            mock_store_permission_group_func = MagicMock()
            mock_store_permission_user_func.return_value = "user_perm"
            mock_store_permission_group_func.return_value = "group_perm"
            mock_get_permission.return_value = Permission(
                name="perm", priority=1, can_read=True, can_update=True, can_delete=True, can_manage=True
            )
            mock_config.PERMISSION_SOURCE_ORDER = ["user", "group"]
            mock_config.DEFAULT_MLFLOW_PERMISSION = "default_perm"

            # user permission found
            result = get_permission_from_store_or_default(
                {"user": mock_store_permission_user_func, "group": mock_store_permission_group_func}
            )
            self.assertTrue(result.permission.can_manage)
            self.assertEqual(result.type, "user")

            # user not found, group found
            mock_store_permission_user_func.side_effect = MlflowException("", RESOURCE_DOES_NOT_EXIST)
            result = get_permission_from_store_or_default(
                {"user": mock_store_permission_user_func, "group": mock_store_permission_group_func}
            )
            self.assertTrue(result.permission.can_manage)
            self.assertEqual(result.type, "group")

            # both not found, fallback to default
            mock_store_permission_group_func.side_effect = MlflowException("", RESOURCE_DOES_NOT_EXIST)
            result = get_permission_from_store_or_default(
                {"user": mock_store_permission_user_func, "group": mock_store_permission_group_func}
            )
            self.assertTrue(result.permission.can_manage)
            self.assertEqual(result.type, "fallback")

            # invalid source in config
            mock_config.PERMISSION_SOURCE_ORDER = ["invalid"]
            # Just call and check fallback, don't assert logs
            result = get_permission_from_store_or_default(
                {"user": mock_store_permission_user_func, "group": mock_store_permission_group_func}
            )
            self.assertEqual(result.type, "fallback")

    @patch("mlflow_oidc_auth.utils.store")
    @patch("mlflow_oidc_auth.utils.get_permission_from_store_or_default")
    def test_can_manage_experiment(self, mock_get_permission_from_store_or_default, mock_store):
        with self.app.test_request_context():
            mock_get_permission_from_store_or_default.return_value = PermissionResult(
                Permission(name="perm", priority=1, can_read=True, can_update=True, can_delete=True, can_manage=True), "user"
            )
            self.assertTrue(can_manage_experiment("exp_id", "user"))
            mock_get_permission_from_store_or_default.return_value = PermissionResult(
                Permission(name="perm", priority=1, can_read=True, can_update=True, can_delete=True, can_manage=False), "user"
            )
            self.assertFalse(can_manage_experiment("exp_id", "user"))

    @patch("mlflow_oidc_auth.utils.store")
    @patch("mlflow_oidc_auth.utils.get_permission_from_store_or_default")
    def test_can_manage_registered_model(self, mock_get_permission_from_store_or_default, mock_store):
        with self.app.test_request_context():
            mock_get_permission_from_store_or_default.return_value = PermissionResult(
                Permission(name="perm", priority=1, can_read=True, can_update=True, can_delete=True, can_manage=True), "user"
            )
            self.assertTrue(can_manage_registered_model("model_name", "user"))
            mock_get_permission_from_store_or_default.return_value = PermissionResult(
                Permission(name="perm", priority=1, can_read=True, can_update=True, can_delete=True, can_manage=False), "user"
            )
            self.assertFalse(can_manage_registered_model("model_name", "user"))

    @patch("mlflow_oidc_auth.utils.store")
    @patch("mlflow_oidc_auth.utils.get_is_admin")
    @patch("mlflow_oidc_auth.utils.get_username")
    @patch("mlflow_oidc_auth.utils.get_experiment_id")
    @patch("mlflow_oidc_auth.utils.can_manage_experiment")
    @patch("mlflow_oidc_auth.utils.make_forbidden_response")
    def test_check_experiment_permission(
        self,
        mock_make_forbidden_response,
        mock_can_manage_experiment,
        mock_get_experiment_id,
        mock_get_username,
        mock_get_is_admin,
        mock_store,
    ):
        with self.app.test_request_context():
            mock_get_is_admin.return_value = False
            mock_get_username.return_value = "user"
            mock_get_experiment_id.return_value = "exp_id"
            mock_can_manage_experiment.return_value = False
            mock_make_forbidden_response.return_value = "forbidden"

            @check_experiment_permission
            def mock_func():
                return "success"

            self.assertEqual(mock_func(), "forbidden")

            mock_can_manage_experiment.return_value = True
            self.assertEqual(mock_func(), "success")

            # Admin always allowed
            mock_get_is_admin.return_value = True
            self.assertEqual(mock_func(), "success")

    @patch("mlflow_oidc_auth.utils.store")
    @patch("mlflow_oidc_auth.utils.get_is_admin")
    @patch("mlflow_oidc_auth.utils.get_username")
    @patch("mlflow_oidc_auth.utils.get_request_param")
    @patch("mlflow_oidc_auth.utils.can_manage_registered_model")
    @patch("mlflow_oidc_auth.utils.make_forbidden_response")
    def test_check_registered_model_permission(
        self,
        mock_make_forbidden_response,
        mock_can_manage_registered_model,
        mock_get_request_param,
        mock_get_username,
        mock_get_is_admin,
        mock_store,
    ):
        with self.app.test_request_context():
            mock_get_is_admin.return_value = False
            mock_get_username.return_value = "user"
            mock_get_request_param.return_value = "model_name"
            mock_can_manage_registered_model.return_value = False
            mock_make_forbidden_response.return_value = "forbidden"

            @check_registered_model_permission
            def mock_func():
                return "success"

            self.assertEqual(mock_func(), "forbidden")

            mock_can_manage_registered_model.return_value = True
            self.assertEqual(mock_func(), "success")

            # Admin always allowed
            mock_get_is_admin.return_value = True
            self.assertEqual(mock_func(), "success")

    @patch("mlflow_oidc_auth.utils.store")
    @patch("mlflow_oidc_auth.utils.get_is_admin")
    @patch("mlflow_oidc_auth.utils.get_username")
    @patch("mlflow_oidc_auth.utils.get_request_param")
    @patch("mlflow_oidc_auth.utils.can_manage_registered_model")
    @patch("mlflow_oidc_auth.utils.make_forbidden_response")
    def test_check_prompt_permission(
        self,
        mock_make_forbidden_response,
        mock_can_manage_registered_model,
        mock_get_request_param,
        mock_get_username,
        mock_get_is_admin,
        mock_store,
    ):
        with self.app.test_request_context():
            mock_get_is_admin.return_value = False
            mock_get_username.return_value = "user"
            mock_get_request_param.return_value = "prompt_name"
            mock_can_manage_registered_model.return_value = False
            mock_make_forbidden_response.return_value = "forbidden"

            @check_prompt_permission
            def mock_func():
                return "success"

            self.assertEqual(mock_func(), "forbidden")

            mock_can_manage_registered_model.return_value = True
            self.assertEqual(mock_func(), "success")

            # Admin always allowed
            mock_get_is_admin.return_value = True
            self.assertEqual(mock_func(), "success")

    def test_get_request_param(self):
        from mlflow_oidc_auth.utils import get_request_param

        # GET method, param present
        with self.app.test_request_context("/?foo=bar", method="GET"):
            self.assertEqual(get_request_param("foo"), "bar")
        # POST method, param present
        with self.app.test_request_context("/", method="POST", json={"foo": "baz"}):
            self.assertEqual(get_request_param("foo"), "baz")
        # param missing, run_id fallback to run_uuid
        with self.app.test_request_context("/", method="GET"):
            with patch("mlflow_oidc_auth.utils.get_request_param", return_value="uuid_val") as mock_get:
                self.assertEqual(get_request_param("run_id"), "uuid_val")
        # param missing, not run_id
        with self.app.test_request_context("/", method="GET"):
            with self.assertRaises(MlflowException) as cm:
                get_request_param("notfound")
            self.assertEqual(cm.exception.error_code, "INVALID_PARAMETER_VALUE")
        # unsupported method
        with self.app.test_request_context("/", method="PUT"):
            with self.assertRaises(MlflowException) as cm:
                get_request_param("foo")
            self.assertEqual(cm.exception.error_code, "BAD_REQUEST")

    def test_get_optional_request_param(self):
        from mlflow_oidc_auth.utils import get_optional_request_param

        # GET method, param present
        with self.app.test_request_context("/?foo=bar", method="GET"):
            self.assertEqual(get_optional_request_param("foo"), "bar")
        # POST method, param present
        with self.app.test_request_context("/", method="POST", json={"foo": "baz"}):
            self.assertEqual(get_optional_request_param("foo"), "baz")
        # param missing
        with self.app.test_request_context("/", method="GET"):
            self.assertIsNone(get_optional_request_param("notfound"))
        # unsupported method
        with self.app.test_request_context("/", method="PUT"):
            with self.assertRaises(MlflowException) as cm:
                get_optional_request_param("foo")
            self.assertEqual(cm.exception.error_code, "BAD_REQUEST")

    @patch("mlflow_oidc_auth.utils._get_tracking_store")
    def test_get_experiment_id(self, mock_tracking_store):
        from mlflow_oidc_auth.utils import get_experiment_id

        # GET method, experiment_id present
        with self.app.test_request_context("/?experiment_id=123", method="GET"):
            self.assertEqual(get_experiment_id(), "123")
        # POST method, experiment_id present
        with self.app.test_request_context("/", method="POST", json={"experiment_id": "456"}):
            self.assertEqual(get_experiment_id(), "456")
        # experiment_name present
        with self.app.test_request_context("/?experiment_name=exp", method="GET"):
            mock_tracking_store().get_experiment_by_name.return_value.experiment_id = "789"
            self.assertEqual(get_experiment_id(), "789")
        # missing both
        with self.app.test_request_context("/", method="GET"):
            with self.assertRaises(MlflowException) as cm:
                get_experiment_id()
            self.assertEqual(cm.exception.error_code, "INVALID_PARAMETER_VALUE")
        # unsupported method
        with self.app.test_request_context("/", method="PUT"):
            with self.assertRaises(MlflowException) as cm:
                get_experiment_id()
            self.assertEqual(cm.exception.error_code, "BAD_REQUEST")

    @patch("mlflow_oidc_auth.utils.store")
    @patch("mlflow_oidc_auth.utils.validate_token")
    def test_get_username(self, mock_validate_token, mock_store):
        from mlflow_oidc_auth.utils import get_username

        with self.app.test_request_context():
            # session username
            with patch("mlflow_oidc_auth.utils.session", {"username": "session_user"}):
                with patch("mlflow_oidc_auth.utils.request") as mock_request:
                    mock_request.authorization = None
                    self.assertEqual(get_username(), "session_user")
            # basic auth username
            with patch("mlflow_oidc_auth.utils.session", {}):

                class AuthBasic:
                    type = "basic"
                    username = "basic_user"

                with patch("mlflow_oidc_auth.utils.request") as mock_request:
                    mock_request.authorization = AuthBasic()
                    self.assertEqual(get_username(), "basic_user")

                # missing username in basic auth
                class AuthBasicNone:
                    type = "basic"
                    username = None

                with patch("mlflow_oidc_auth.utils.request") as mock_request:
                    mock_request.authorization = AuthBasicNone()
                    with self.assertRaises(MlflowException):
                        get_username()
            # bearer token
            with patch("mlflow_oidc_auth.utils.session", {}):

                class AuthBearer:
                    type = "bearer"
                    token = "tok"

                mock_validate_token.return_value = {"email": "bearer_user"}
                with patch("mlflow_oidc_auth.utils.request") as mock_request:
                    mock_request.authorization = AuthBearer()
                    self.assertEqual(get_username(), "bearer_user")
            # no auth
            with patch("mlflow_oidc_auth.utils.session", {}):
                with patch("mlflow_oidc_auth.utils.request") as mock_request:
                    mock_request.authorization = None
                    with self.assertRaises(MlflowException):
                        get_username()

    @patch("mlflow_oidc_auth.utils._get_tracking_store")
    def test_get_experiment_id_experiment_name_not_found(self, mock_tracking_store):
        from mlflow_oidc_auth.utils import get_experiment_id

        # experiment_name provided but not found
        with self.app.test_request_context("/?experiment_name=nonexistent_exp", method="GET"):
            mock_tracking_store().get_experiment_by_name.return_value = None
            with self.assertRaises(MlflowException) as cm:
                get_experiment_id()
            self.assertEqual(cm.exception.error_code, "INVALID_PARAMETER_VALUE")


if __name__ == "__main__":
    unittest.main()
