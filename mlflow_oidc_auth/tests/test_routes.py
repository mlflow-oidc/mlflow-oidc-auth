from unittest import mock
from mlflow_oidc_auth import routes

"""
`routes` contains mutiple routes definitions.
This test is to ensure that all expected routes are present.
"""


class TestRoutes:
    def test_routes_presented(self):
        assert all(
            route is not None
            for route in [
                routes.HOME,
                routes.LOGIN,
                routes.LOGOUT,
                routes.CALLBACK,
                routes.STATIC,
                routes.UI,
                routes.UI_ROOT,
                routes.GET_ACCESS_TOKEN,
                routes.GET_CURRENT_USER,
                routes.GET_EXPERIMENTS,
                routes.GET_MODELS,
                routes.GET_USERS,
                routes.GET_USER_EXPERIMENTS,
                routes.GET_USER_MODELS,
                routes.GET_EXPERIMENT_USERS,
                routes.GET_MODEL_USERS,
                routes.CREATE_USER,
                routes.GET_USER,
                routes.UPDATE_USER_PASSWORD,
                routes.UPDATE_USER_ADMIN,
                routes.DELETE_USER,
                routes.CREATE_EXPERIMENT_PERMISSION,
                routes.GET_EXPERIMENT_PERMISSION,
                routes.UPDATE_EXPERIMENT_PERMISSION,
                routes.DELETE_EXPERIMENT_PERMISSION,
                routes.CREATE_REGISTERED_MODEL_PERMISSION,
                routes.GET_REGISTERED_MODEL_PERMISSION,
                routes.UPDATE_REGISTERED_MODEL_PERMISSION,
                routes.DELETE_REGISTERED_MODEL_PERMISSION,
                routes.GET_GROUPS,
                routes.GET_GROUP_USERS,
                routes.GET_GROUP_EXPERIMENTS_PERMISSION,
                routes.CREATE_GROUP_EXPERIMENT_PERMISSION,
                routes.DELETE_GROUP_EXPERIMENT_PERMISSION,
                routes.UPDATE_GROUP_EXPERIMENT_PERMISSION,
                routes.GET_GROUP_MODELS_PERMISSION,
                routes.CREATE_GROUP_MODEL_PERMISSION,
                routes.DELETE_GROUP_MODEL_PERMISSION,
                routes.UPDATE_GROUP_MODEL_PERMISSION,
            ]
        )
