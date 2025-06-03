from flask import jsonify
from mlflow.server.handlers import catch_mlflow_exception

from mlflow_oidc_auth.store import store
from mlflow_oidc_auth.utils import (
    can_manage_registered_model,
    check_registered_model_permission,
    get_is_admin,
    get_request_param,
    get_username,
)


@catch_mlflow_exception
@check_registered_model_permission
def create_group_model_permission(group_name: str, registered_model_name: str):
    store.create_group_model_permission(group_name, registered_model_name, get_request_param("permission"))
    return jsonify({"message": "Group model permission has been created."})


@catch_mlflow_exception
@check_registered_model_permission
def delete_group_model_permission(group_name: str, registered_model_name: str):
    store.delete_group_model_permission(group_name, registered_model_name)
    return jsonify({"message": "Group model permission has been deleted."})


@catch_mlflow_exception
@check_registered_model_permission
def update_group_model_permission(group_name: str, registered_model_name: str):
    store.update_group_model_permission(group_name, registered_model_name, get_request_param("permission"))
    return jsonify({"message": "Group model permission has been updated."})


@catch_mlflow_exception
def list_group_models(group_name: str):
    models = store.get_group_models(group_name)
    if get_is_admin():
        return jsonify(
            [
                {
                    "name": model.name,
                    "permission": model.permission,
                }
                for model in models
            ]
        )
    current_user = store.get_user(get_username())
    return jsonify(
        [
            {
                "name": model.name,
                "permission": model.permission,
            }
            for model in models
            if can_manage_registered_model(
                model.name,
                current_user.username,
            )
        ]
    )
