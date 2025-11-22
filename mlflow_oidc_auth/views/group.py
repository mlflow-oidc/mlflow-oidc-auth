from flask import jsonify
from mlflow.server.handlers import catch_mlflow_exception

from mlflow_oidc_auth.store import store
from mlflow_oidc_auth.utils.request_helpers import get_is_admin, get_username


@catch_mlflow_exception
def list_groups():
    is_admin = get_is_admin()
    if is_admin:
        return store.get_groups()
    else:
        # Security fix: Non-admin users should only see groups they belong to
        return store.get_groups_for_user(get_username())


@catch_mlflow_exception
def get_group_users(group_name):
    return jsonify({"users": store.get_group_users(group_name)})
