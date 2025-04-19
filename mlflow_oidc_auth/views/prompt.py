from flask import jsonify, make_response
from mlflow.server.handlers import _get_model_registry_store, catch_mlflow_exception

from mlflow_oidc_auth.responses.client_error import make_forbidden_response
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
def create_prompt_permission():
    store.create_registered_model_permission(
        name=get_request_param("name"),
        username=get_request_param("username"),
        permission=get_request_param("permission"),
    )
    return jsonify({"message": "Model permission has been created."})


@catch_mlflow_exception
@check_registered_model_permission
def get_prompt_permission():
    rmp = store.get_registered_model_permission(get_request_param("name"), get_request_param("username"))
    return make_response({"prompt_permission": rmp.to_json()})


@catch_mlflow_exception
@check_registered_model_permission
def update_prompt_permission():
    store.update_registered_model_permission(
        get_request_param("name"), get_request_param("username"), get_request_param("permission")
    )
    return make_response(jsonify({"message": "Model permission has been changed"}))


@catch_mlflow_exception
@check_registered_model_permission
def delete_prompt_permission():
    store.delete_registered_model_permission(get_request_param("name"), get_request_param("username"))
    return make_response(jsonify({"message": "Model permission has been deleted"}))


@catch_mlflow_exception
def get_prompts():
    if get_is_admin():
        prompts = _get_model_registry_store().search_registered_models(
            max_results=1000, filter_string="tags.`mlflow.prompt.is_prompt` = 'true'"
        )
    else:
        current_user = store.get_user(get_username())
        prompts = []
        for model in _get_model_registry_store().search_registered_models(
            max_results=1000, filter_string="tags.`mlflow.prompt.is_prompt` = 'true'"
        ):
            if can_manage_registered_model(model.name, current_user.username):
                prompts.append(model)
    models = [
        {
            "name": model.name,
            "tags": model.tags,
            "description": model.description,
            "aliases": model.aliases,
        }
        for model in prompts
    ]
    return jsonify(models)


@catch_mlflow_exception
def get_prompt_users(prompt_name):
    if not get_is_admin():
        current_user = store.get_user(get_username())
        if not can_manage_registered_model(prompt_name, current_user.username):
            return make_forbidden_response()
    list_users = store.list_users()
    # Filter users who are associated with the given model
    users = []
    for user in list_users:
        # Check if the user is associated with the model
        user_models = (
            {model.name: model.permission for model in user.registered_model_permissions}
            if user.registered_model_permissions
            else {}
        )
        if prompt_name in user_models:
            users.append({"username": user.username, "permission": user_models[prompt_name]})
    return jsonify(users)
