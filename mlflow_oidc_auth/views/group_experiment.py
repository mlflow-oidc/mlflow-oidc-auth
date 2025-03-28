from flask import jsonify
from mlflow.server.handlers import _get_tracking_store, catch_mlflow_exception

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
def create_group_experiment_permission(group_name):
    store.create_group_experiment_permission(group_name, get_experiment_id(), get_request_param("permission"))
    return jsonify({"message": "Group experiment permission has been created."})


@catch_mlflow_exception
@check_experiment_permission
def update_group_experiment_permission(group_name):
    store.update_group_experiment_permission(group_name, get_experiment_id(), get_request_param("permission"))
    return jsonify({"message": "Group experiment permission has been updated."})


@catch_mlflow_exception
@check_experiment_permission
def delete_group_experiment_permission(group_name):
    store.delete_group_experiment_permission(group_name, get_experiment_id())
    return jsonify({"message": "Group experiment permission has been deleted."})


@catch_mlflow_exception
def get_group_experiments(group_name):
    experiments = store.get_group_experiments(group_name)
    if get_is_admin():
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
    current_user = store.get_user(get_username())
    return jsonify(
        [
            {
                "id": experiment.experiment_id,
                "name": _get_tracking_store().get_experiment(experiment.experiment_id).name,
                "permission": experiment.permission,
            }
            for experiment in experiments
            if can_manage_experiment(
                experiment.experiment_id,
                current_user.username,
            )
        ]
    )
