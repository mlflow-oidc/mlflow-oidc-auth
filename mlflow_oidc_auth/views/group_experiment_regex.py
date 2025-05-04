from flask import jsonify
from mlflow.server.handlers import _get_tracking_store, catch_mlflow_exception

from mlflow_oidc_auth.store import store
from mlflow_oidc_auth.utils import (
    can_manage_experiment,
    check_admin_permission,
    get_experiment_id,
    get_is_admin,
    get_request_param,
    get_username,
)


@catch_mlflow_exception
@check_admin_permission
def create_group_experiment_regex_permission(group_name):
    store.create_group_experiment_regex_permission(
        group_name=group_name,
        regex=get_request_param("regex"),
        priority=int(get_request_param("priority")),
        permission=get_request_param("permission"),
    )
    return jsonify({"status": "success"}), 200


@catch_mlflow_exception
@check_admin_permission
def get_group_experiment_regex_permission():
    ep = store.get_group_experiment_regex_permission(
        group_name=get_request_param("group_name"),
        regex=get_request_param("regex"),
    )
    return jsonify({"experiment_permission": ep.to_json()}), 200


@catch_mlflow_exception
@check_admin_permission
def update_group_experiment_regex_permission():
    ep = store.update_group_experiment_regex_permission(
        group_name=get_request_param("group_name"),
        regex=get_request_param("regex"),
        priority=int(get_request_param("priority")),
        permission=get_request_param("permission"),
    )
    return jsonify({"experiment_permission": ep.to_json()}), 200


@catch_mlflow_exception
@check_admin_permission
def delete_group_experiment_regex_permission():
    store.delete_group_experiment_regex_permission(
        group_name=get_request_param("group_name"),
        regex=get_request_param("regex"),
    )
    return jsonify({"status": "success"}), 200
