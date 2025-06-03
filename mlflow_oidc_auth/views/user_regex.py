from flask import jsonify
from mlflow.server.handlers import catch_mlflow_exception

from mlflow_oidc_auth.store import store
from mlflow_oidc_auth.utils import check_admin_permission


@catch_mlflow_exception
@check_admin_permission
def list_user_experiment_regex_permission(username: str):
    ep = store.list_experiment_regex_permissions(username=username)
    return jsonify([e.to_json() for e in ep]), 200


@catch_mlflow_exception
@check_admin_permission
def get_user_experiment_regex_permission(username: str, pattern_id: str):
    ep = store.get_experiment_regex_permission(id=int(pattern_id), username=username)
    if ep is None:
        return jsonify({"error": "Experiment regex permission not found"}), 404
    return jsonify(ep.to_json()), 200
