from flask import jsonify, make_response
from mlflow.server.handlers import _get_model_registry_store, catch_mlflow_exception

from mlflow_oidc_auth.store import store
from mlflow_oidc_auth.utils import (
    check_admin_permission,
    get_request_param,
)


@catch_mlflow_exception
@check_admin_permission
def create_registered_model_regex_permission():
    store.create_registered_model_regex_permission(
        regex=get_request_param("regex"),
        priority=int(get_request_param("priority")),
        permission=get_request_param("permission"),
        username=get_request_param("username"),
    )
    return jsonify({"status": "success"}), 200


@catch_mlflow_exception
@check_admin_permission
def get_registered_model_regex_permission():
    rm = store.get_registered_model_regex_permission(
        regex=get_request_param("regex"),
        username=get_request_param("username"),
    )
    return make_response({"registered_model_permission": rm.to_json()})


@catch_mlflow_exception
@check_admin_permission
def update_registered_model_regex_permission():
    rm = store.update_registered_model_regex_permission(
        regex=get_request_param("regex"),
        priority=int(get_request_param("priority")),
        permission=get_request_param("permission"),
        username=get_request_param("username"),
    )
    return make_response({"registered_model_permission": rm.to_json()})


@catch_mlflow_exception
@check_admin_permission
def delete_registered_model_regex_permission():
    store.delete_registered_model_regex_permission(
        regex=get_request_param("regex"),
        username=get_request_param("username"),
    )
    return make_response({"status": "success"})
