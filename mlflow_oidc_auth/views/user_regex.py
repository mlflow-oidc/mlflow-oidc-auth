from flask import jsonify
from mlflow.server.handlers import catch_mlflow_exception

from mlflow_oidc_auth.store import store
from mlflow_oidc_auth.utils import check_admin_permission, get_request_param


@catch_mlflow_exception
@check_admin_permission
def list_user_experiment_regex_permission(username: str):
    ep = store.list_experiment_regex_permissions(username=username)
    return jsonify([e.to_json() for e in ep]), 200


@catch_mlflow_exception
@check_admin_permission
def get_user_experiment_regex_permission(username: str, pattern_id: str):
    ep = store.get_experiment_regex_permission(id=int(pattern_id), username=username)
    if ep is None:
        return jsonify({"error": "Experiment regex permission not found"}), 404
    return jsonify(ep.to_json()), 200


# @catch_mlflow_exception
# @check_admin_permission
# def create_user_registered_model_regex_permission(username: str):
#     store.create_registered_model_regex_permission(
#         regex=get_request_param("regex"),
#         priority=int(get_request_param("priority")),
#         permission=get_request_param("permission"),
#         username=username,
#     )
#     return jsonify({"status": "success"}), 200


# @catch_mlflow_exception
# @check_admin_permission
# def get_user_registered_model_regex_permission(username):
#     rm = store.list_registered_model_regex_permissions(username=username)
#     return jsonify([r.to_json() for r in rm]), 200


# @catch_mlflow_exception
# @check_admin_permission
# def update_user_registered_model_regex_permission(username):
#     rm = store.update_registered_model_regex_permission(
#         regex=get_request_param("regex"),
#         priority=int(get_request_param("priority")),
#         permission=get_request_param("permission"),
#         username=username,
#     )
#     return jsonify(rm.to_json()), 200


# @catch_mlflow_exception
# @check_admin_permission
# def delete_user_registered_model_regex_permission(username):
#     store.delete_registered_model_regex_permission(regex=get_request_param("regex"), username=username)
#     return jsonify({"status": "success"}), 200


# @catch_mlflow_exception
# @check_admin_permission
# def create_user_prompt_regex_permission(username):
#     store.create_prompt_regex_permission(
#         regex=get_request_param("regex"),
#         priority=int(get_request_param("priority")),
#         permission=get_request_param("permission"),
#         username=username,
#     )
#     return jsonify({"status": "success"}), 200


# @catch_mlflow_exception
# @check_admin_permission
# def get_user_prompt_regex_permission(username):
#     rm = store.list_prompt_regex_permissions(username=username)
#     return jsonify([r.to_json() for r in rm]), 200


# @catch_mlflow_exception
# @check_admin_permission
# def update_user_prompt_regex_permission(username):
#     rm = store.update_prompt_regex_permission(
#         regex=get_request_param("regex"),
#         priority=int(get_request_param("priority")),
#         permission=get_request_param("permission"),
#         username=username,
#     )
#     return jsonify(rm.to_json()), 200


# @catch_mlflow_exception
# @check_admin_permission
# def delete_user_prompt_regex_permission(username):
#     store.delete_prompt_regex_permission(regex=get_request_param("regex"), username=username)
#     return jsonify({"status": "success"}), 200
