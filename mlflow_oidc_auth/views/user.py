from flask import jsonify
from mlflow.server.handlers import _get_model_registry_store, _get_tracking_store, catch_mlflow_exception

from mlflow_oidc_auth.permissions import NO_PERMISSIONS
from mlflow_oidc_auth.store import store
from mlflow_oidc_auth.user import create_user, generate_token
from mlflow_oidc_auth.utils import (
    get_is_admin,
    get_permission_from_store_or_default,
    get_request_param,
    get_optional_request_param,
    get_username,
)


@catch_mlflow_exception
def create_new_user():
    username = get_request_param("username")
    display_name = get_request_param("display_name")
    is_admin = bool(get_optional_request_param("is_admin") or False)
    is_service_account = bool(get_optional_request_param("is_service_account") or False)
    status, message = create_user(username, display_name, is_admin, is_service_account)
    if status:
        return (jsonify({"message": message}), 201)
    else:
        return (jsonify({"message": message}), 200)


@catch_mlflow_exception
def get_user():
    username = get_request_param("username")
    user = store.get_user(username)
    return jsonify({"user": user.to_json()})


@catch_mlflow_exception
def delete_user():
    username = get_request_param("username")
    store.delete_user(username)
    return jsonify({"message": f"Account {username} has been deleted"})


@catch_mlflow_exception
def create_access_token():
    new_token = generate_token()
    store.update_user(get_username(), new_token)
    return jsonify({"token": new_token})


@catch_mlflow_exception
def update_username_password():
    new_password = generate_token()
    store.update_user(get_username(), new_password)
    return jsonify({"token": new_password})


@catch_mlflow_exception
def get_user_experiments(username):
    current_user = store.get_user(get_username())
    all_experiments = _get_tracking_store().search_experiments()
    is_admin = get_is_admin()

    if is_admin:
        list_experiments = all_experiments
    else:
        if username == current_user.username:
            list_experiments = [
                exp
                for exp in all_experiments
                if get_permission_from_store_or_default(
                    lambda: store.get_experiment_permission(exp.experiment_id, username).permission,
                    lambda: store.get_user_groups_experiment_permission(exp.experiment_id, username).permission,
                ).permission.name
                != NO_PERMISSIONS.name
            ]
        else:
            list_experiments = [
                exp
                for exp in all_experiments
                if get_permission_from_store_or_default(
                    lambda: store.get_experiment_permission(exp.experiment_id, current_user.username).permission,
                    lambda: store.get_user_groups_experiment_permission(exp.experiment_id, current_user.username).permission,
                ).permission.can_manage
            ]

    experiments_list = [
        {
            "name": _get_tracking_store().get_experiment(exp.experiment_id).name,
            "id": exp.experiment_id,
            "permission": (
                perm := get_permission_from_store_or_default(
                    lambda: store.get_experiment_permission(exp.experiment_id, username).permission,
                    lambda: store.get_user_groups_experiment_permission(exp.experiment_id, username).permission,
                )
            ).permission.name,
            "type": perm.type,
        }
        for exp in list_experiments
    ]
    return jsonify({"experiments": experiments_list})


@catch_mlflow_exception
def get_user_models(username):
    all_registered_models = _get_model_registry_store().search_registered_models(max_results=1000)
    current_user = store.get_user(get_username())
    is_admin = get_is_admin()
    if is_admin:
        list_registered_models = all_registered_models
    else:
        if username == current_user.username:
            list_registered_models = [
                model
                for model in all_registered_models
                if get_permission_from_store_or_default(
                    lambda: store.get_registered_model_permission(model.name, username).permission,
                    lambda: store.get_user_groups_registered_model_permission(model.name, username).permission,
                ).permission.name
                != NO_PERMISSIONS.name
            ]
        else:
            list_registered_models = [
                model
                for model in all_registered_models
                if get_permission_from_store_or_default(
                    lambda: store.get_registered_model_permission(model.name, current_user.username).permission,
                    lambda: store.get_user_groups_registered_model_permission(model.name, current_user.username).permission,
                ).permission.can_manage
            ]
    models = [
        {
            "name": model.name,
            "permission": (
                perm := get_permission_from_store_or_default(
                    lambda: store.get_registered_model_permission(model.name, username).permission,
                    lambda: store.get_user_groups_registered_model_permission(model.name, username).permission,
                )
            ).permission.name,
            "type": perm.type,
        }
        for model in list_registered_models
    ]
    return jsonify({"models": models})


@catch_mlflow_exception
def get_user_prompts(username):
    all_registered_models = _get_model_registry_store().search_registered_models(
        max_results=1000, filter_string="tags.`mlflow.prompt.is_prompt` = 'true'"
    )
    current_user = store.get_user(get_username())
    is_admin = get_is_admin()
    if is_admin:
        list_registered_models = all_registered_models
    else:
        if username == current_user.username:
            list_registered_models = [
                model
                for model in all_registered_models
                if get_permission_from_store_or_default(
                    lambda: store.get_registered_model_permission(model.name, username).permission,
                    lambda: store.get_user_groups_registered_model_permission(model.name, username).permission,
                ).permission.name
                != NO_PERMISSIONS.name
            ]
        else:
            list_registered_models = [
                model
                for model in all_registered_models
                if get_permission_from_store_or_default(
                    lambda: store.get_registered_model_permission(model.name, current_user.username).permission,
                    lambda: store.get_user_groups_registered_model_permission(model.name, current_user.username).permission,
                ).permission.can_manage
            ]
    models = [
        {
            "name": model.name,
            "permission": (
                perm := get_permission_from_store_or_default(
                    lambda: store.get_registered_model_permission(model.name, username).permission,
                    lambda: store.get_user_groups_registered_model_permission(model.name, username).permission,
                )
            ).permission.name,
            "type": perm.type,
        }
        for model in list_registered_models
    ]
    return jsonify({"prompts": models})


@catch_mlflow_exception
def get_users():
    service_account = bool(get_optional_request_param("service") or False)
    # is_admin = get_is_admin()
    # if is_admin:
    #     users = [user.username for user in store.list_users()]
    # else:
    #     users = [get_username()]
    users = [user.username for user in store.list_users(is_service_account=service_account)]
    return jsonify({"users": users})


@catch_mlflow_exception
def update_user_admin():
    is_admin = get_request_param("is_admin")
    store.update_user(get_username(), is_admin)
    return jsonify({"is_admin": is_admin})


@catch_mlflow_exception
def get_current_user():
    return store.get_user(get_username()).to_json()
