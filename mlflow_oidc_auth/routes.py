from mlflow.server.handlers import _get_rest_path

HOME = "/"
LOGIN = "/login"
LOGOUT = "/logout"
CALLBACK = "/callback"

STATIC = "/oidc/static/<path:filename>"
UI = "/oidc/ui/<path:filename>"
UI_ROOT = "/oidc/ui/"

# Runtime configuration endpoint under UI path
UI_CONFIG = "/oidc/ui/config.json"

########### API refactoring ###########
# USER, EXPERIMENT, PATTERN
USER_EXPERIMENT_PERMISSIONS = _get_rest_path("/mlflow/permissions/users/<string:username>/experiments")
USER_EXPERIMENT_PERMISSION_DETAIL = _get_rest_path("/mlflow/permissions/users/<string:username>/experiments/<string:experiment_id>")

EXPERIMENT_USER_PERMISSIONS = _get_rest_path("/mlflow/permissions/experiments/<string:experiment_id>/users")
EXPERIMENT_USER_PERMISSION_DETAIL = _get_rest_path("/mlflow/permissions/experiments/<string:experiment_id>/users/<string:username>")

USER_EXPERIMENT_PATTERN_PERMISSIONS = _get_rest_path("/mlflow/permissions/users/<string:username>/experiment-patterns")
USER_EXPERIMENT_PATTERN_PERMISSION_DETAIL = _get_rest_path("/mlflow/permissions/users/<string:username>/experiment-patterns/<string:pattern_id>")

# USER, REGISTERED_MODEL, PATTERN
USER_REGISTERED_MODEL_PERMISSIONS = _get_rest_path("/mlflow/permissions/users/<string:username>/registered-models")
USER_REGISTERED_MODEL_PERMISSION_DETAIL = _get_rest_path("/mlflow/permissions/users/<string:username>/registered-models/<string:name>")

REGISTERED_MODEL_USER_PERMISSIONS = _get_rest_path("/mlflow/permissions/registered-models/<string:name>/users")
REGISTERED_MODEL_USER_PERMISSION_DETAIL = _get_rest_path("/mlflow/permissions/registered-models/<string:name>/users/<string:username>")

USER_REGISTERED_MODEL_PATTERN_PERMISSIONS = _get_rest_path("/mlflow/permissions/users/<string:username>/registered-models-patterns")
USER_REGISTERED_MODEL_PATTERN_PERMISSION_DETAIL = _get_rest_path("/mlflow/permissions/users/<string:username>/registered-models-patterns/<string:pattern_id>")

# USER, PROMPT, PATTERN
USER_PROMPT_PERMISSIONS = _get_rest_path("/mlflow/permissions/users/<string:username>/prompts")
USER_PROMPT_PERMISSION_DETAIL = _get_rest_path("/mlflow/permissions/users/<string:username>/prompts/<string:prompt_name>")

PROMPT_USER_PERMISSIONS = _get_rest_path("/mlflow/permissions/prompts/<string:prompt_name>/users")
PROMPT_USER_PERMISSION_DETAIL = _get_rest_path("/mlflow/permissions/prompts/<string:prompt_name>/users/<string:username>")

USER_PROMPT_PATTERN_PERMISSIONS = _get_rest_path("/mlflow/permissions/users/<string:username>/prompts-patterns")
USER_PROMPT_PATTERN_PERMISSION_DETAIL = _get_rest_path("/mlflow/permissions/users/<string:username>/prompts-patterns/<string:pattern_id>")

# GROUP STUFF

# GROUP -> EXPERIMENT, REGISTERED_MODEL, PROMPT
# GROUP, EXPERIMENT, PATTERN
GROUP_EXPERIMENT_PERMISSIONS = _get_rest_path("/mlflow/permissions/groups/<string:group_name>/experiments")
GROUP_EXPERIMENT_PERMISSION_DETAIL = _get_rest_path("/mlflow/permissions/groups/<string:group_name>/experiments/<string:experiment_id>")

EXPERIMENT_GROUP_PERMISSIONS = _get_rest_path("/mlflow/permissions/experiments/<string:experiment_id>/groups")
EXPERIMENT_GROUP_PERMISSION_DETAIL = _get_rest_path("/mlflow/permissions/experiments/<string:experiment_id>/groups/<string:group_name>")

GROUP_EXPERIMENT_PATTERN_PERMISSIONS = _get_rest_path("/mlflow/permissions/groups/<string:group_name>/experiment-patterns")
GROUP_EXPERIMENT_PATTERN_PERMISSION_DETAIL = _get_rest_path("/mlflow/permissions/groups/<string:group_name>/experiment-patterns/<string:pattern_id>")

# GROUP, REGISTERED_MODEL, PATTERN
GROUP_REGISTERED_MODEL_PERMISSIONS = _get_rest_path("/mlflow/permissions/groups/<string:group_name>/registered-models")
GROUP_REGISTERED_MODEL_PERMISSION_DETAIL = _get_rest_path("/mlflow/permissions/groups/<string:group_name>/registered-models/<string:name>")

REGISTERED_MODEL_GROUP_PERMISSIONS = _get_rest_path("/mlflow/permissions/registered-models/<string:name>/groups")
REGISTERED_MODEL_GROUP_PERMISSION_DETAIL = _get_rest_path("/mlflow/permissions/registered-models/<string:name>/groups/<string:group_name>")

GROUP_REGISTERED_MODEL_PATTERN_PERMISSIONS = _get_rest_path("/mlflow/permissions/groups/<string:group_name>/registered-models-patterns")
GROUP_REGISTERED_MODEL_PATTERN_PERMISSION_DETAIL = _get_rest_path(
    "/mlflow/permissions/groups/<string:group_name>/registered-models-patterns/<string:pattern_id>"
)

# GROUP, PROMPT, PATTERN
GROUP_PROMPT_PERMISSIONS = _get_rest_path("/mlflow/permissions/groups/<string:group_name>/prompts")
GROUP_PROMPT_PERMISSION_DETAIL = _get_rest_path("/mlflow/permissions/groups/<string:group_name>/prompts/<string:prompt_name>")

PROMPT_GROUP_PERMISSIONS = _get_rest_path("/mlflow/permissions/prompts/<string:prompt_name>/groups")
PROMPT_GROUP_PERMISSION_DETAIL = _get_rest_path("/mlflow/permissions/prompts/<string:prompt_name>/groups/<string:group_name>")

GROUP_PROMPT_PATTERN_PERMISSIONS = _get_rest_path("/mlflow/permissions/groups/<string:group_name>/prompts-patterns")
GROUP_PROMPT_PATTERN_PERMISSION_DETAIL = _get_rest_path("/mlflow/permissions/groups/<string:group_name>/prompts-patterns/<string:pattern_id>")

#######################################

# List of Resources

LIST_EXPERIMENTS = _get_rest_path("/mlflow/permissions/experiments")
LIST_PROMPTS = _get_rest_path("/mlflow/permissions/prompts")
LIST_MODELS = _get_rest_path("/mlflow/permissions/registered-models")
LIST_USERS = _get_rest_path("/mlflow/permissions/users")
LIST_GROUPS = _get_rest_path("/mlflow/permissions/groups")

GROUP_USER_PERMISSIONS = _get_rest_path("/mlflow/permissions/groups/<string:group_name>/users")
###############


# create access token for current user
CREATE_ACCESS_TOKEN = _get_rest_path("/mlflow/permissions/users/access-token")
# get infrmation about current user
GET_CURRENT_USER = _get_rest_path("/mlflow/permissions/users/current")

# CRUD routes from basic_auth
CREATE_USER = _get_rest_path("/mlflow/users/create")
GET_USER = _get_rest_path("/mlflow/users/get")
UPDATE_USER_PASSWORD = _get_rest_path("/mlflow/users/update-password")
UPDATE_USER_ADMIN = _get_rest_path("/mlflow/users/update-admin")
DELETE_USER = _get_rest_path("/mlflow/users/delete")
