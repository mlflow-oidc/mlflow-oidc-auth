from flask import jsonify
from mlflow.server.handlers import catch_mlflow_exception

from mlflow_oidc_auth.store import store
from mlflow_oidc_auth.utils import check_admin_permission, get_request_param


@catch_mlflow_exception
@check_admin_permission
def create_prompt_regex_permission(username: str):
    store.create_prompt_regex_permission(
        regex=get_request_param("regex"),
        priority=int(get_request_param("priority")),
        permission=get_request_param("permission"),
        username=username,
    )
    return jsonify({"status": "success"}), 200


@catch_mlflow_exception
@check_admin_permission
def list_prompt_regex_permissions(username: str):
    rm = store.list_prompt_regex_permissions(
        username=username,
    )
    return jsonify({"prompt_permissions": [r.to_json() for r in rm]}), 200


@catch_mlflow_exception
@check_admin_permission
def get_prompt_regex_permission(username: str, pattern_id: str):
    rm = store.get_prompt_regex_permission(
        id=int(pattern_id),
        username=username,
    )
    return jsonify({"prompt_permission": rm.to_json()}), 200


@catch_mlflow_exception
@check_admin_permission
def update_prompt_regex_permission(username: str, pattern_id: str):
    rm = store.update_prompt_regex_permission(
        id=int(pattern_id),
        regex=get_request_param("regex"),
        priority=int(get_request_param("priority")),
        permission=get_request_param("permission"),
        username=username,
    )
    return jsonify({"prompt_permission": rm.to_json()}), 200


@catch_mlflow_exception
@check_admin_permission
def delete_prompt_regex_permission(username: str, pattern_id: str):
    store.delete_prompt_regex_permission(
        id=int(pattern_id),
        username=username,
    )
    return jsonify({"status": "success"}), 200
