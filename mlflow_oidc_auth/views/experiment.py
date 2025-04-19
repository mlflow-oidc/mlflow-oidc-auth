from flask import jsonify, make_response
from mlflow.server.handlers import _get_tracking_store, catch_mlflow_exception

from mlflow_oidc_auth.responses.client_error import make_forbidden_response
from mlflow_oidc_auth.store import store
from mlflow_oidc_auth.utils import (
    can_manage_experiment,
    check_experiment_permission,
    get_experiment_id,
    get_is_admin,
    get_request_param,
    get_username,
)


@catch_mlflow_exception
@check_experiment_permission
def create_experiment_permission():
    store.create_experiment_permission(
        get_experiment_id(),
        get_request_param("username"),
        get_request_param("permission"),
    )
    return jsonify({"message": "Experiment permission has been created."})


@catch_mlflow_exception
@check_experiment_permission
def get_experiment_permission():
    ep = store.get_experiment_permission(get_experiment_id(), get_request_param("username"))
    return make_response({"experiment_permission": ep.to_json()})


@catch_mlflow_exception
@check_experiment_permission
def update_experiment_permission():
    store.update_experiment_permission(
        get_experiment_id(),
        get_request_param("username"),
        get_request_param("permission"),
    )
    return jsonify({"message": "Experiment permission has been changed."})


@catch_mlflow_exception
@check_experiment_permission
def delete_experiment_permission():
    store.delete_experiment_permission(
        get_experiment_id(),
        get_request_param("username"),
    )
    return jsonify({"message": "Experiment permission has been deleted."})


@catch_mlflow_exception
def get_experiments():
    if get_is_admin():
        list_experiments = _get_tracking_store().search_experiments()
    else:
        current_user = store.get_user(get_username())
        list_experiments = []
        for experiment in _get_tracking_store().search_experiments():
            if can_manage_experiment(experiment.experiment_id, current_user.username):
                list_experiments.append(experiment)
    experiments = [
        {
            "name": experiment.name,
            "id": experiment.experiment_id,
            "tags": experiment.tags,
        }
        for experiment in list_experiments
    ]
    return jsonify(experiments)


@catch_mlflow_exception
def get_experiment_users(experiment_id: str):
    experiment_id = str(experiment_id)
    if not get_is_admin():
        current_user = store.get_user(get_username())
        if not can_manage_experiment(experiment_id, current_user.username):
            return make_forbidden_response()
    list_users = store.list_users()
    # Filter users who are associated with the given experiment
    users = []
    for user in list_users:
        # Check if the user is associated with the experiment
        user_experiments_details = {str(exp.experiment_id): exp.permission for exp in (user.experiment_permissions or [])}
        if experiment_id in user_experiments_details:
            users.append({"username": user.username, "permission": user_experiments_details[experiment_id]})
    return jsonify(users)
