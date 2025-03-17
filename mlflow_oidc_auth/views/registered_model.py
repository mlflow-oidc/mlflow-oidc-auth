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
def create_registered_model_permission():
    store.create_registered_model_permission(
        get_request_param("name"), get_request_param("user_name"), get_request_param("permission")
    )
    return jsonify({"message": "Model permission has been created."})


@catch_mlflow_exception
@check_registered_model_permission
def get_registered_model_permission():
    rmp = store.get_registered_model_permission(get_request_param("name"), get_request_param("user_name"))
    return make_response({"registered_model_permission": rmp.to_json()})


@catch_mlflow_exception
@check_registered_model_permission
def update_registered_model_permission():
    store.update_registered_model_permission(
        get_request_param("name"), get_request_param("user_name"), get_request_param("permission")
    )
    return make_response(jsonify({"message": "Model permission has been changed"}))


@catch_mlflow_exception
@check_registered_model_permission
def delete_registered_model_permission():
    store.delete_registered_model_permission(get_request_param("name"), get_request_param("user_name"))
    return make_response(jsonify({"message": "Model permission has been deleted"}))


@catch_mlflow_exception
def get_registered_models():
    if get_is_admin():
        registered_models = _get_model_registry_store().search_registered_models(max_results=1000)
    else:
        current_user = store.get_user(get_username())
        registered_models = []
        for model in _get_model_registry_store().search_registered_models(max_results=1000):
            if can_manage_registered_model(model.name, current_user.username):
                registered_models.append(model)
    models = [
        {
            "name": model.name,
            "tags": model.tags,
            "description": model.description,
            "aliases": model.aliases,
        }
        for model in registered_models
    ]
    return jsonify(models)


@catch_mlflow_exception
def get_registered_model_users(model_name):
    if not get_is_admin():
        current_user = store.get_user(get_username())
        if not can_manage_registered_model(model_name, current_user.username):
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
        if model_name in user_models:
            users.append({"username": user.username, "permission": user_models[model_name]})
    return jsonify(users)
