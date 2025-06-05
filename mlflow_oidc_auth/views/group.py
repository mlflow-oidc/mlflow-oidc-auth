from flask import jsonify
from mlflow.server.handlers import catch_mlflow_exception

from mlflow_oidc_auth.store import store


@catch_mlflow_exception
def list_groups():
    return store.get_groups()


@catch_mlflow_exception
def get_group_users(group_name):
    return jsonify({"users": store.get_group_users(group_name)})
