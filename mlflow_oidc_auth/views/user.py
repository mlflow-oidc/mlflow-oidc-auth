from datetime import datetime, timedelta, timezone

from flask import jsonify
from mlflow.server.handlers import _get_model_registry_store, _get_tracking_store, catch_mlflow_exception

from mlflow_oidc_auth.permissions import NO_PERMISSIONS
from mlflow_oidc_auth.store import store
from mlflow_oidc_auth.user import create_user, generate_token
from mlflow_oidc_auth.utils import (
    effective_experiment_permission,
    effective_prompt_permission,
    effective_registered_model_permission,
    get_is_admin,
    get_optional_request_param,
    get_request_param,
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
def create_user_access_token():
    username = get_request_param("username")
    expiration_str = get_request_param("expiration")
    # Handle ISO 8601 with 'Z' (UTC) at the end
    if expiration_str:
        if expiration_str.endswith("Z"):
            expiration_str = expiration_str[:-1] + "+00:00"
        expiration = datetime.fromisoformat(expiration_str)
        now = datetime.now(timezone.utc)
        if expiration < now:
            return jsonify({"message": "Expiration date must be in the future"}), 400
        if expiration > now + timedelta(days=366):
            return jsonify({"message": "Expiration date must be less than 1 year in the future"}), 400
    else:
        expiration = None
    user = store.get_user(username)
    if user is None:
        return jsonify({"message": f"User {username} not found"}), 404
    new_token = generate_token()
    store.update_user(username=username, password=new_token, password_expiration=expiration)
    return jsonify({"token": new_token, "message": f"Token for {username} has been created"})


@catch_mlflow_exception
def update_username_password():
    new_password = generate_token()
    store.update_user(username=get_username(), password=new_password)
    return jsonify({"token": new_password})


# TODO: move filtering logic to store
@catch_mlflow_exception
def list_user_experiments(username):
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
                if effective_experiment_permission(exp.experiment_id, username).permission.name != NO_PERMISSIONS.name
            ]
        else:
            list_experiments = [
                exp
                for exp in all_experiments
                if effective_experiment_permission(exp.experiment_id, current_user.username).permission.can_manage
            ]

    experiments_list = [
        {
            "name": _get_tracking_store().get_experiment(exp.experiment_id).name,
            "id": exp.experiment_id,
            "permission": (perm := effective_experiment_permission(exp.experiment_id, username)).permission.name,
            "type": perm.type,
        }
        for exp in list_experiments
    ]
    return jsonify({"experiments": experiments_list})


@catch_mlflow_exception
def list_user_models(username):
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
                if effective_registered_model_permission(model.name, username).permission.name != NO_PERMISSIONS.name
            ]
        else:
            list_registered_models = [
                model
                for model in all_registered_models
                if effective_registered_model_permission(model.name, current_user.username).permission.can_manage
            ]
    models = [
        {
            "name": model.name,
            "permission": (perm := effective_registered_model_permission(model.name, username)).permission.name,
            "type": perm.type,
        }
        for model in list_registered_models
    ]
    return jsonify({"models": models})


@catch_mlflow_exception
def list_user_prompts(username):
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
                if effective_prompt_permission(model.name, username).permission.name != NO_PERMISSIONS.name
            ]
        else:
            list_registered_models = [
                model
                for model in all_registered_models
                if effective_prompt_permission(model.name, current_user.username).permission.can_manage
            ]
    models = [
        {
            "name": model.name,
            "permission": (perm := effective_prompt_permission(model.name, username)).permission.name,
            "type": perm.type,
        }
        for model in list_registered_models
    ]
    return jsonify({"prompts": models})


# TODO: use to_json
@catch_mlflow_exception
def list_users():
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
    is_admin = get_request_param("is_admin").strip().lower() == "true" if get_request_param("is_admin") else False
    store.update_user(username=get_username(), is_admin=is_admin)
    return jsonify({"is_admin": is_admin})


@catch_mlflow_exception
def get_current_user():
    return store.get_user(get_username()).to_json()
