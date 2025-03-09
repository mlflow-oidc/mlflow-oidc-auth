from flask import jsonify
from mlflow.server.handlers import _get_tracking_store, catch_mlflow_exception

from mlflow_oidc_auth.store import store
from mlflow_oidc_auth.utils import get_request_param, get_username, get_is_admin, get_permission_from_store_or_default


@catch_mlflow_exception
def create_group_experiment_permission(group_name):
    experiment_id = get_request_param("experiment_id")
    new_permission = get_request_param("permission")
    current_user = store.get_user(get_username())
    is_admin = get_is_admin()
    if is_admin:
        store.create_group_experiment_permission(group_name, experiment_id, new_permission)
    else:
        permission = get_permission_from_store_or_default(
            lambda: store.get_experiment_permission(experiment_id, current_user.username).permission,
            lambda: store.get_user_groups_experiment_permission(experiment_id, current_user.username).permission,
        ).permission
        if permission.can_manage:
            store.create_group_experiment_permission(group_name, experiment_id, new_permission)
        else:
            return jsonify({"message": "You do not have permission to create experiment permission."})
    return jsonify({"message": "Group experiment permission has been created."})


@catch_mlflow_exception
def update_group_experiment_permission(group_name):
    experiment_id = get_request_param("experiment_id")
    new_permission = get_request_param("permission")
    current_user = store.get_user(get_username())
    is_admin = get_is_admin()
    if is_admin:
        store.update_group_experiment_permission(group_name, experiment_id, new_permission)
    else:
        permission = get_permission_from_store_or_default(
            lambda: store.get_experiment_permission(experiment_id, current_user.username).permission,
            lambda: store.get_user_groups_experiment_permission(experiment_id, current_user.username).permission,
        ).permission
        if permission.can_manage:
            store.update_group_experiment_permission(group_name, experiment_id, new_permission)
        else:
            return jsonify({"message": "You do not have permission to update experiment permission."})
    return jsonify({"message": "Group experiment permission has been updated."})


@catch_mlflow_exception
def delete_group_experiment_permission(group_name):
    experiment_id = get_request_param("experiment_id")
    current_user = store.get_user(get_username())
    is_admin = get_is_admin()
    if is_admin:
        store.delete_group_experiment_permission(group_name, experiment_id)
    else:
        permission = get_permission_from_store_or_default(
            lambda: store.get_experiment_permission(experiment_id, current_user.username).permission,
            lambda: store.get_user_groups_experiment_permission(experiment_id, current_user.username).permission,
        ).permission
        if permission.can_manage:
            store.delete_group_experiment_permission(group_name, experiment_id)
        else:
            return jsonify({"message": "You do not have permission to delete experiment permission."})
    return jsonify({"message": "Group experiment permission has been deleted."})


@catch_mlflow_exception
def create_group_model_permission(group_name):
    model_name = get_request_param("model_name")
    new_permission = get_request_param("permission")
    current_user = store.get_user(get_username())
    is_admin = get_is_admin()
    if is_admin:
        store.create_group_model_permission(group_name, model_name, new_permission)
    else:
        permission = get_permission_from_store_or_default(
            lambda: store.get_model_permission(model_name, current_user.username).permission,
            lambda: store.get_user_groups_model_permission(model_name, current_user.username).permission,
        ).permission
        if permission.can_manage:
            store.create_group_model_permission(group_name, model_name, new_permission)
        else:
            return jsonify({"message": "You do not have permission to create model permission."})
    return jsonify({"message": "Group model permission has been created."})


@catch_mlflow_exception
def delete_group_model_permission(group_name):
    model_name = get_request_param("model_name")
    current_user = store.get_user(get_username())
    is_admin = get_is_admin()
    if is_admin:
        store.delete_group_model_permission(group_name, model_name)
    else:
        permission = get_permission_from_store_or_default(
            lambda: store.get_model_permission(model_name, current_user.username).permission,
            lambda: store.get_user_groups_model_permission(model_name, current_user.username).permission,
        ).permission
        if permission.can_manage:
            store.delete_group_model_permission(group_name, model_name)
        else:
            return jsonify({"message": "You do not have permission to delete model permission."})
    return jsonify({"message": "Group model permission has been deleted."})


@catch_mlflow_exception
def update_group_model_permission(group_name):
    model_name = get_request_param("model_name")
    new_permission = get_request_param("permission")
    current_user = store.get_user(get_username())
    is_admin = get_is_admin()
    if is_admin:
        store.update_group_model_permission(group_name, model_name, new_permission)
    else:
        permission = get_permission_from_store_or_default(
            lambda: store.get_registered_model_permission(model_name, current_user.username).permission,
            lambda: store.get_user_groups_registered_model_permission(model_name, current_user.username).permission,
        ).permission
        if permission.can_manage:
            store.update_group_model_permission(group_name, model_name, new_permission)
        else:
            return jsonify({"message": "You do not have permission to update model permission."})
    return jsonify({"message": "Group model permission has been updated."})


@catch_mlflow_exception
def get_groups():
    groups = store.get_groups()
    return jsonify({"groups": groups})


@catch_mlflow_exception
def get_group_users(group_name):
    users = store.get_group_users(group_name)
    return jsonify({"users": users})


@catch_mlflow_exception
def get_group_experiments(group_name):
    experiments = store.get_group_experiments(group_name)
    current_user = store.get_user(get_username())
    is_admin = get_is_admin()
    if is_admin:
        return jsonify(
            [
                {
                    "id": experiment.experiment_id,
                    "name": _get_tracking_store().get_experiment(experiment.experiment_id).name,
                    "permission": experiment.permission,
                }
                for experiment in experiments
            ]
        )
    return jsonify(
        [
            {
                "id": experiment.experiment_id,
                "name": _get_tracking_store().get_experiment(experiment.experiment_id).name,
                "permission": experiment.permission,
            }
            for experiment in experiments
            if get_permission_from_store_or_default(
                lambda: store.get_experiment_permission(experiment.experiment_id, current_user.username).permission,
                lambda: store.get_user_groups_experiment_permission(experiment.experiment_id, current_user.username).permission,
            ).permission.can_manage
        ]
    )


@catch_mlflow_exception
def get_group_models(group_name):
    models = store.get_group_models(group_name)
    current_user = store.get_user(get_username())
    is_admin = get_is_admin()
    if is_admin:
        return jsonify(
            [
                {
                    "name": model.name,
                    "permission": model.permission,
                }
                for model in models
            ]
        )
    return jsonify(
        [
            {
                "name": model.name,
                "permission": model.permission,
            }
            for model in models
            if get_permission_from_store_or_default(
                lambda: store.get_registered_model_permission(model.name, current_user.username).permission,
                lambda: store.get_user_groups_registered_model_permission(model.name, current_user.username).permission,
            ).permission.can_manage
        ]
    )
