from flask import jsonify
from mlflow.server.handlers import catch_mlflow_exception

from mlflow_oidc_auth.store import store
from mlflow_oidc_auth.utils import (
    can_manage_registered_model,
    check_prompt_permission,
    get_is_admin,
    get_request_param,
    get_username,
)


@catch_mlflow_exception
@check_prompt_permission
def create_group_prompt_permission(group_name):
    store.create_group_prompt_permission(
        group_name=group_name, name=get_request_param("name"), permission=get_request_param("permission")
    )
    return jsonify({"message": "Group model permission has been created."})


@catch_mlflow_exception
@check_prompt_permission
def delete_group_prompt_permission(group_name):
    store.delete_group_prompt_permission(group_name, get_request_param("name"))
    return jsonify({"message": "Group model permission has been deleted."})


@catch_mlflow_exception
@check_prompt_permission
def update_group_prompt_permission(group_name):
    store.update_group_prompt_permission(group_name, get_request_param("name"), get_request_param("permission"))
    return jsonify({"message": "Group model permission has been updated."})


@catch_mlflow_exception
def get_group_prompts(group_name):
    models = store.get_group_prompts(group_name)
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
