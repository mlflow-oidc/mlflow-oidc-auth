from mlflow.exceptions import RestException
from mlflow.utils.credentials import get_default_host_creds
from mlflow.utils.rest_utils import http_request_safe

from mlflow_oidc_auth.entities import ExperimentPermission, RegisteredModelPermission, User
from mlflow_oidc_auth.routes import (
    CREATE_EXPERIMENT_PERMISSION,
    CREATE_REGISTERED_MODEL_PERMISSION,
    CREATE_USER,
    DELETE_EXPERIMENT_PERMISSION,
    DELETE_REGISTERED_MODEL_PERMISSION,
    DELETE_USER,
    GET_EXPERIMENT_PERMISSION,
    GET_REGISTERED_MODEL_PERMISSION,
    GET_USER,
    UPDATE_EXPERIMENT_PERMISSION,
    UPDATE_REGISTERED_MODEL_PERMISSION,
    UPDATE_USER_ADMIN,
    UPDATE_USER_PASSWORD,
)


class AuthServiceClient:
    """
    Client of an MLflow Tracking Server that enabled the default basic authentication plugin.
    It is recommended to use :py:func:`mlflow.server.get_app_client()` to instantiate this class.
    See https://mlflow.org/docs/latest/auth.html for more information.
    """

    def __init__(self, tracking_uri: str):
        """
        Args:
            tracking_uri: Address of local or remote tracking server.
        """
        self.tracking_uri = tracking_uri

    def _request(self, endpoint, method, **kwargs):
        host_creds = get_default_host_creds(self.tracking_uri)
        resp = http_request_safe(host_creds, endpoint, method, **kwargs)
        return resp.json()

    def create_user(self, username: str, password: str):
        """
        Create a new user.

        Args:
            username: The username.
            password: The user's password. Must not be empty string.
        """
        # Input validation
        if not username:
            raise ValueError("Username must not be empty.")
        if not password:
            raise ValueError("Password must not be empty.")

        try:
            resp = self._request(
                CREATE_USER,
                "POST",
                json={"username": username, "password": password},
            )
        except RestException as e:
            raise e

        return User.from_json(resp["user"])

    def get_user(self, username: str):
        """
        Get a user with a specific username.

        Args:
            username: The username.
        """
        if not username:
            raise ValueError("Username must not be empty.")

        try:
            resp = self._request(
                GET_USER,
                "GET",
                params={"username": username},
            )
        except RestException as e:
            raise e

        return User.from_json(resp["user"])

    def update_user_password(self, username: str, password: str):
        """
        Update the password of a specific user.

        Args:
            username: The username.
            password: The new password.
        """
        if not username:
            raise ValueError("Username must not be empty.")
        if not password:
            raise ValueError("Password must not be empty.")

        try:
            self._request(
                UPDATE_USER_PASSWORD,
                "PATCH",
                json={"username": username, "password": password},
            )
        except RestException as e:
            raise e

    def update_user_admin(self, username: str, is_admin: bool):
        """
        Update the admin status of a specific user.

        Args:
            username: The username.
            is_admin: The new admin status.
        """
        if not username:
            raise ValueError("Username must not be empty.")
        if not isinstance(is_admin, bool):
            raise ValueError("is_admin must be a boolean value.")

        try:
            self._request(
                UPDATE_USER_ADMIN,
                "PATCH",
                json={"username": username, "is_admin": is_admin},
            )
        except RestException as e:
            raise e

    def delete_user(self, username: str):
        """
        Delete a specific user.

        Args:
            username: The username.
        """
        if not username:
            raise ValueError("Username must not be empty.")

        try:
            self._request(
                DELETE_USER,
                "DELETE",
                json={"username": username},
            )
        except RestException as e:
            raise e

    def create_experiment_permission(self, experiment_id: str, username: str, permission: str):
        """
        Create a permission on an experiment for a user.

        Args:
            experiment_id: The id of the experiment.
            username: The username.
            permission: Permission to grant. Must be one of "READ", "EDIT", "MANAGE" and
                "NO_PERMISSIONS".
        """
        if not experiment_id:
            raise ValueError("Experiment ID must not be empty.")
        if not username:
            raise ValueError("Username must not be empty.")
        if permission not in ["READ", "EDIT", "MANAGE", "NO_PERMISSIONS"]:
            raise ValueError("Permission must be one of 'READ', 'EDIT', 'MANAGE', or 'NO_PERMISSIONS'.")

        try:
            resp = self._request(
                CREATE_EXPERIMENT_PERMISSION,
                "POST",
                json={
                    "experiment_id": experiment_id,
                    "username": username,
                    "permission": permission,
                },
            )
        except RestException as e:
            raise e

        return ExperimentPermission.from_json(resp["experiment_permission"])

    def get_experiment_permission(self, experiment_id: str, username: str):
        """
        Get an experiment permission for a user.

        Args:
            experiment_id: The id of the experiment.
            username: The username.
        """
        if not experiment_id:
            raise ValueError("Experiment ID must not be empty.")
        if not username:
            raise ValueError("Username must not be empty.")

        try:
            resp = self._request(
                GET_EXPERIMENT_PERMISSION,
                "GET",
                params={"experiment_id": experiment_id, "username": username},
            )
        except RestException as e:
            # Add more specific error handling here if needed
            raise e

        return ExperimentPermission.from_json(resp["experiment_permission"])

    def update_experiment_permission(self, experiment_id: str, username: str, permission: str):
        """
        Update an existing experiment permission for a user.

        Args:
            experiment_id: The id of the experiment.
            username: The username.
            permission: New permission to grant. Must be one of "READ", "EDIT", "MANAGE" and
                "NO_PERMISSIONS".
        """
        if not experiment_id:
            raise ValueError("Experiment ID must not be empty.")
        if not username:
            raise ValueError("Username must not be empty.")
        if permission not in ["READ", "EDIT", "MANAGE", "NO_PERMISSIONS"]:
            raise ValueError("Permission must be one of 'READ', 'EDIT', 'MANAGE', or 'NO_PERMISSIONS'.")

        try:
            self._request(
                UPDATE_EXPERIMENT_PERMISSION,
                "PATCH",
                json={
                    "experiment_id": experiment_id,
                    "username": username,
                    "permission": permission,
                },
            )
        except RestException as e:
            raise e

    def delete_experiment_permission(self, experiment_id: str, username: str):
        """
        Delete an existing experiment permission for a user.

        Args:
            experiment_id: The id of the experiment.
            username: The username.
        """
        if not experiment_id:
            raise ValueError("Experiment ID must not be empty.")
        if not username:
            raise ValueError("Username must not be empty.")

        try:
            self._request(
                DELETE_EXPERIMENT_PERMISSION,
                "DELETE",
                json={"experiment_id": experiment_id, "username": username},
            )
        except RestException as e:
            raise e

    def create_registered_model_permission(self, name: str, username: str, permission: str):
        """
        Create a permission on an registered model for a user.

        Args:
            name: The name of the registered model.
            username: The username.
            permission: Permission to grant. Must be one of "READ", "EDIT", "MANAGE" and
                "NO_PERMISSIONS".
        """
        if not name:
            raise ValueError("Name must not be empty.")
        if not username:
            raise ValueError("Username must not be empty.")
        if permission not in ["READ", "EDIT", "MANAGE", "NO_PERMISSIONS"]:
            raise ValueError("Permission must be one of 'READ', 'EDIT', 'MANAGE', or 'NO_PERMISSIONS'.")

        try:
            resp = self._request(
                CREATE_REGISTERED_MODEL_PERMISSION,
                "POST",
                json={"name": name, "username": username, "permission": permission},
            )
        except RestException as e:
            raise e

        return RegisteredModelPermission.from_json(resp["registered_model_permission"])

    def get_registered_model_permission(self, name: str, username: str):
        """
        Get an registered model permission for a user.

        Args:
            name: The name of the registered model.
            username: The username.
        """
        if not name:
            raise ValueError("Name must not be empty.")
        if not username:
            raise ValueError("Username must not be empty.")

        try:
            resp = self._request(
                GET_REGISTERED_MODEL_PERMISSION,
                "GET",
                params={"name": name, "username": username},
            )
        except RestException as e:
            raise e

        return RegisteredModelPermission.from_json(resp["registered_model_permission"])

    def update_registered_model_permission(self, name: str, username: str, permission: str):
        """
        Update an existing registered model permission for a user.

        Args:
            name: The name of the registered model.
            username: The username.
            permission: New permission to grant. Must be one of "READ", "EDIT", "MANAGE" and
                "NO_PERMISSIONS".
        """
        if not name:
            raise ValueError("Name must not be empty.")
        if not username:
            raise ValueError("Username must not be empty.")
        if permission not in ["READ", "EDIT", "MANAGE", "NO_PERMISSIONS"]:
            raise ValueError("Permission must be one of 'READ', 'EDIT', 'MANAGE', or 'NO_PERMISSIONS'.")

        try:
            self._request(
                UPDATE_REGISTERED_MODEL_PERMISSION,
                "PATCH",
                json={"name": name, "username": username, "permission": permission},
            )
        except RestException as e:
            raise e

    def delete_registered_model_permission(self, name: str, username: str):
        """
        Delete an existing registered model permission for a user.

        Args:
            name: The name of the registered model.
            username: The username.
        """
        if not name:
            raise ValueError("Name must not be empty.")
        if not username:
            raise ValueError("Username must not be empty.")

        try:
            self._request(
                DELETE_REGISTERED_MODEL_PERMISSION,
                "DELETE",
                json={"name": name, "username": username},
            )
        except RestException as e:
            raise e
