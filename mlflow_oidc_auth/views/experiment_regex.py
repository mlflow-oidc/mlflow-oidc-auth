from flask import jsonify, make_response
from mlflow.server.handlers import catch_mlflow_exception

from mlflow_oidc_auth.store import store
from mlflow_oidc_auth.utils import check_admin_permission, get_request_param


@catch_mlflow_exception
@check_admin_permission
def create_experiment_regex_permission():
    store.create_experiment_regex_permission(
        get_request_param("regex"),
        int(get_request_param("priority")),
        get_request_param("permission"),
        get_request_param("username"),
    )
    return jsonify({"status": "success"}), 200


@catch_mlflow_exception
@check_admin_permission
def get_experiment_regex_permission():
    ep = store.get_experiment_regex_permission(
        get_request_param("regex"),
        get_request_param("username"),
    )
    return make_response({"experiment_permission": ep.to_json()})


@catch_mlflow_exception
@check_admin_permission
def update_experiment_regex_permission():
    ep = store.update_experiment_regex_permission(
        get_request_param("regex"),
        int(get_request_param("priority")),
        get_request_param("permission"),
        get_request_param("username"),
    )
    return make_response({"experiment_permission": ep.to_json()})


@catch_mlflow_exception
@check_admin_permission
def delete_experiment_regex_permission():
    store.delete_experiment_regex_permission(
        get_request_param("regex"),
        get_request_param("username"),
    )
    return make_response({"status": "success"})
