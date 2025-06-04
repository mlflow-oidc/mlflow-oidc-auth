from flask import jsonify
from mlflow.server.handlers import catch_mlflow_exception

from mlflow_oidc_auth.store import store
from mlflow_oidc_auth.utils import check_admin_permission, get_request_param


@catch_mlflow_exception
@check_admin_permission
def create_group_prompt_regex_permission(group_name):
    store.create_group_prompt_regex_permission(
        group_name=group_name,
        regex=get_request_param("regex"),
        priority=int(get_request_param("priority")),
        permission=get_request_param("permission"),
    )
    return jsonify({"status": "success"}), 200


@catch_mlflow_exception
@check_admin_permission
def list_group_prompt_regex_permissions(group_name):
    ep = store.list_group_prompt_regex_permissions(
        group_name=group_name,
    )
    return [e.to_json() for e in ep] if ep else jsonify({"error": "No permissions found"}), 200


@catch_mlflow_exception
@check_admin_permission
def get_group_prompt_regex_permission(group_name: str, pattern_id: str):
    ep = store.get_group_prompt_regex_permission(
        group_name=group_name,
        id=int(pattern_id),
    )
    return jsonify({"prompt_permission": ep.to_json()}), 200


@catch_mlflow_exception
@check_admin_permission
def update_group_prompt_regex_permission(group_name: str, pattern_id: str):
    ep = store.update_group_prompt_regex_permission(
        group_name=group_name,
        id=int(pattern_id),
        regex=get_request_param("regex"),
        priority=int(get_request_param("priority")),
        permission=get_request_param("permission"),
    )
    return jsonify({"prompt_permission": ep.to_json()}), 200


@catch_mlflow_exception
@check_admin_permission
def delete_group_prompt_regex_permission(group_name: str, pattern_id: str):
    store.delete_group_prompt_regex_permission(
        group_name=group_name,
        id=int(pattern_id),
    )
    return jsonify({"status": "success"}), 200
