import unittest
from unittest.mock import patch, MagicMock
from flask import Flask
from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import RESOURCE_DOES_NOT_EXIST
from mlflow_oidc_auth.utils import (
    get_is_admin,
    get_permission_from_store_or_default,
    can_manage_experiment,
    can_manage_registered_model,
    check_experiment_permission,
    check_registered_model_permission,
    PermissionResult,
)
from mlflow_oidc_auth.permissions import Permission


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
            mock_config.DEFAULT_MLFLOW_PERMISSION = "default_perm"

            result = get_permission_from_store_or_default(mock_store_permission_user_func, mock_store_permission_group_func)
            self.assertTrue(result.permission.can_manage)

            mock_store_permission_user_func.side_effect = MlflowException("", RESOURCE_DOES_NOT_EXIST)
            result = get_permission_from_store_or_default(mock_store_permission_user_func, mock_store_permission_group_func)
            self.assertTrue(result.permission.can_manage)

            mock_store_permission_group_func.side_effect = MlflowException("", RESOURCE_DOES_NOT_EXIST)
            result = get_permission_from_store_or_default(mock_store_permission_user_func, mock_store_permission_group_func)
            self.assertTrue(result.permission.can_manage)

    @patch("mlflow_oidc_auth.utils.store")
    @patch("mlflow_oidc_auth.utils.get_permission_from_store_or_default")
    def test_can_manage_experiment(self, mock_get_permission_from_store_or_default, mock_store):
        with self.app.test_request_context():
            mock_get_permission_from_store_or_default.return_value = PermissionResult(
                Permission(name="perm", priority=1, can_read=True, can_update=True, can_delete=True, can_manage=True), "user"
            )
            self.assertTrue(can_manage_experiment("exp_id", "user"))

    @patch("mlflow_oidc_auth.utils.store")
    @patch("mlflow_oidc_auth.utils.get_permission_from_store_or_default")
    def test_can_manage_registered_model(self, mock_get_permission_from_store_or_default, mock_store):
        with self.app.test_request_context():
            mock_get_permission_from_store_or_default.return_value = PermissionResult(
                Permission(name="perm", priority=1, can_read=True, can_update=True, can_delete=True, can_manage=True), "user"
            )
            self.assertTrue(can_manage_registered_model("model_name", "user"))

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


if __name__ == "__main__":
    unittest.main()
