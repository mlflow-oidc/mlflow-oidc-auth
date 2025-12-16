from unittest import mock
from mlflow_oidc_auth import routes

"""
`routes` contains multiple routes definitions after refactoring.
This test ensures that all expected routes are present and properly defined.
"""


class TestRoutes:
    def test_routes_presented(self):
        assert all(
            route is not None
            for route in [
                # Basic auth routes
                routes.HOME,
                routes.LOGIN,
                routes.LOGOUT,
                routes.CALLBACK,
                # OTLP ingest
                routes.OTLP_TRACES,
                routes.STATIC,
                routes.UI,
                routes.UI_ROOT,
                # User management routes
                routes.CREATE_ACCESS_TOKEN,
                routes.GET_CURRENT_USER,
                routes.CREATE_USER,
                routes.GET_USER,
                routes.UPDATE_USER_PASSWORD,
                routes.UPDATE_USER_ADMIN,
                routes.DELETE_USER,
                # List resources
                routes.LIST_EXPERIMENTS,
                routes.LIST_PROMPTS,
                routes.LIST_MODELS,
                routes.LIST_USERS,
                routes.LIST_GROUPS,
                # User permissions
                routes.USER_EXPERIMENT_PERMISSIONS,
                routes.USER_EXPERIMENT_PERMISSION_DETAIL,
                routes.USER_REGISTERED_MODEL_PERMISSIONS,
                routes.USER_REGISTERED_MODEL_PERMISSION_DETAIL,
                routes.USER_PROMPT_PERMISSIONS,
                routes.USER_PROMPT_PERMISSION_DETAIL,
                # Resource user permissions
                routes.EXPERIMENT_USER_PERMISSIONS,
                routes.EXPERIMENT_USER_PERMISSION_DETAIL,
                routes.REGISTERED_MODEL_USER_PERMISSIONS,
                routes.REGISTERED_MODEL_USER_PERMISSION_DETAIL,
                routes.PROMPT_USER_PERMISSIONS,
                routes.PROMPT_USER_PERMISSION_DETAIL,
                # User pattern permissions
                routes.USER_EXPERIMENT_PATTERN_PERMISSIONS,
                routes.USER_EXPERIMENT_PATTERN_PERMISSION_DETAIL,
                routes.USER_REGISTERED_MODEL_PATTERN_PERMISSIONS,
                routes.USER_REGISTERED_MODEL_PATTERN_PERMISSION_DETAIL,
                routes.USER_PROMPT_PATTERN_PERMISSIONS,
                routes.USER_PROMPT_PATTERN_PERMISSION_DETAIL,
                # Group permissions
                routes.GROUP_EXPERIMENT_PERMISSIONS,
                routes.GROUP_EXPERIMENT_PERMISSION_DETAIL,
                routes.GROUP_REGISTERED_MODEL_PERMISSIONS,
                routes.GROUP_REGISTERED_MODEL_PERMISSION_DETAIL,
                routes.GROUP_PROMPT_PERMISSIONS,
                routes.GROUP_PROMPT_PERMISSION_DETAIL,
                # Resource group permissions
                routes.EXPERIMENT_GROUP_PERMISSIONS,
                routes.EXPERIMENT_GROUP_PERMISSION_DETAIL,
                routes.REGISTERED_MODEL_GROUP_PERMISSIONS,
                routes.REGISTERED_MODEL_GROUP_PERMISSION_DETAIL,
                routes.PROMPT_GROUP_PERMISSIONS,
                routes.PROMPT_GROUP_PERMISSION_DETAIL,
                # Group pattern permissions
                routes.GROUP_EXPERIMENT_PATTERN_PERMISSIONS,
                routes.GROUP_EXPERIMENT_PATTERN_PERMISSION_DETAIL,
                routes.GROUP_REGISTERED_MODEL_PATTERN_PERMISSIONS,
                routes.GROUP_REGISTERED_MODEL_PATTERN_PERMISSION_DETAIL,
                routes.GROUP_PROMPT_PATTERN_PERMISSIONS,
                routes.GROUP_PROMPT_PATTERN_PERMISSION_DETAIL,
                # Group user permissions
                routes.GROUP_USER_PERMISSIONS,
            ]
        )
