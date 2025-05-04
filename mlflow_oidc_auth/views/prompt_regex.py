from flask import jsonify
from mlflow.server.handlers import catch_mlflow_exception

from mlflow_oidc_auth.store import store
from mlflow_oidc_auth.utils import (
    check_admin_permission,
    get_request_param,
)


@catch_mlflow_exception
@check_admin_permission
def create_prompt_regex_permission():
    store.create_prompt_regex_permission(
        regex=get_request_param("regex"),
        priority=int(get_request_param("priority")),
        permission=get_request_param("permission"),
        username=get_request_param("username"),
    )
    return jsonify({"status": "success"}), 200


@catch_mlflow_exception
@check_admin_permission
def get_prompt_regex_permission():
    rm = store.get_prompt_regex_permission(
        regex=get_request_param("regex"),
        username=get_request_param("username"),
    )
    return jsonify({"prompt_permission": rm.to_json()}), 200


@catch_mlflow_exception
@check_admin_permission
def update_prompt_regex_permission():
    rm = store.update_prompt_regex_permission(
        regex=get_request_param("regex"),
        priority=int(get_request_param("priority")),
        permission=get_request_param("permission"),
        username=get_request_param("username"),
    )
    return jsonify({"prompt_permission": rm.to_json()}), 200


@catch_mlflow_exception
@check_admin_permission
def delete_prompt_regex_permission():
    store.delete_prompt_regex_permission(
        regex=get_request_param("regex"),
        username=get_request_param("username"),
    )
    return jsonify({"status": "success"}), 200
