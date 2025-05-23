from mlflow.server.handlers import _get_rest_path

HOME = "/"
LOGIN = "/login"
LOGOUT = "/logout"
CALLBACK = "/callback"

STATIC = "/oidc/static/<path:filename>"
UI = "/oidc/ui/<path:filename>"
UI_ROOT = "/oidc/ui/"

# create access token for current user
CREATE_ACCESS_TOKEN = _get_rest_path("/mlflow/users/access-token")
# get infrmation about current user
GET_CURRENT_USER = _get_rest_path("/mlflow/users/current")
# list of experiments, models, users
GET_EXPERIMENTS = _get_rest_path("/mlflow/experiments")
GET_PROMPTS = _get_rest_path("/mlflow/prompts")
GET_MODELS = _get_rest_path("/mlflow/registered-models")
GET_USERS = _get_rest_path("/mlflow/users")
# list of experiments, models, filtered by user
GET_USER_EXPERIMENTS = _get_rest_path("/mlflow/users/<string:username>/experiments")
GET_USER_PROMPTS = _get_rest_path("/mlflow/users/<string:username>/prompts")
GET_USER_MODELS = _get_rest_path("/mlflow/users/<string:username>/registered-models")
# list of users filtered by experiment, model
GET_EXPERIMENT_USERS = _get_rest_path("/mlflow/experiments/<int:experiment_id>/users")
GET_PROMPT_USERS = _get_rest_path("/mlflow/prompts/<string:prompt_name>/users")
GET_MODEL_USERS = _get_rest_path("/mlflow/registered-models/<string:model_name>/users")

# CRUD routes from basic_auth
CREATE_USER = _get_rest_path("/mlflow/users/create")
GET_USER = _get_rest_path("/mlflow/users/get")
UPDATE_USER_PASSWORD = _get_rest_path("/mlflow/users/update-password")
UPDATE_USER_ADMIN = _get_rest_path("/mlflow/users/update-admin")
DELETE_USER = _get_rest_path("/mlflow/users/delete")

CREATE_EXPERIMENT_PERMISSION = _get_rest_path("/mlflow/experiments/permissions/create")
GET_EXPERIMENT_PERMISSION = _get_rest_path("/mlflow/experiments/permissions/get")
UPDATE_EXPERIMENT_PERMISSION = _get_rest_path("/mlflow/experiments/permissions/update")
DELETE_EXPERIMENT_PERMISSION = _get_rest_path("/mlflow/experiments/permissions/delete")

CREATE_PROMPT_PERMISSION = _get_rest_path("/mlflow/prompts/permissions/create")
GET_PROMPT_PERMISSION = _get_rest_path("/mlflow/prompts/permissions/get")
UPDATE_PROMPT_PERMISSION = _get_rest_path("/mlflow/prompts/permissions/update")
DELETE_PROMPT_PERMISSION = _get_rest_path("/mlflow/prompts/permissions/delete")

CREATE_REGISTERED_MODEL_PERMISSION = _get_rest_path("/mlflow/registered-models/permissions/create")
GET_REGISTERED_MODEL_PERMISSION = _get_rest_path("/mlflow/registered-models/permissions/get")
UPDATE_REGISTERED_MODEL_PERMISSION = _get_rest_path("/mlflow/registered-models/permissions/update")
DELETE_REGISTERED_MODEL_PERMISSION = _get_rest_path("/mlflow/registered-models/permissions/delete")

CREATE_EXPERIMENT_REGEX_PERMISSION = _get_rest_path("/mlflow/experiments/regex-permissions/create")
GET_EXPERIMENT_REGEX_PERMISSION = _get_rest_path("/mlflow/experiments/regex-permissions/get")
UPDATE_EXPERIMENT_REGEX_PERMISSION = _get_rest_path("/mlflow/experiments/regex-permissions/update")
DELETE_EXPERIMENT_REGEX_PERMISSION = _get_rest_path("/mlflow/experiments/regex-permissions/delete")

CREATE_REGISTERED_MODEL_REGEX_PERMISSION = _get_rest_path("/mlflow/registered-models/regex-permissions/create")
GET_REGISTERED_MODEL_REGEX_PERMISSION = _get_rest_path("/mlflow/registered-models/regex-permissions/get")
UPDATE_REGISTERED_MODEL_REGEX_PERMISSION = _get_rest_path("/mlflow/registered-models/regex-permissions/update")
DELETE_REGISTERED_MODEL_REGEX_PERMISSION = _get_rest_path("/mlflow/registered-models/regex-permissions/delete")

CREATE_PROMPT_REGEX_PERMISSION = _get_rest_path("/mlflow/prompts/regex-permissions/create")
GET_PROMPT_REGEX_PERMISSION = _get_rest_path("/mlflow/prompts/regex-permissions/get")
UPDATE_PROMPT_REGEX_PERMISSION = _get_rest_path("/mlflow/prompts/regex-permissions/update")
DELETE_PROMPT_REGEX_PERMISSION = _get_rest_path("/mlflow/prompts/regex-permissions/delete")

CREATE_USER_EXPERIMENT_REGEX_PERMISSION = _get_rest_path("/mlflow/users/<string:username>/experiments/regex/create")
GET_USER_EXPERIMENT_REGEX_PERMISSION = _get_rest_path("/mlflow/users/<string:username>/experiments/regex")
UPDATE_USER_EXPERIMENT_REGEX_PERMISSION = _get_rest_path("/mlflow/users/<string:username>/experiments/regex/update")
DELETE_USER_EXPERIMENT_REGEX_PERMISSION = _get_rest_path("/mlflow/users/<string:username>/experiments/regex/delete")

CREATE_USER_REGISTERED_MODEL_REGEX_PERMISSION = _get_rest_path("/mlflow/users/<string:username>/registered-models/regex/create")
GET_USER_REGISTERED_MODEL_REGEX_PERMISSION = _get_rest_path("/mlflow/users/<string:username>/registered-models/regex")
UPDATE_USER_REGISTERED_MODEL_REGEX_PERMISSION = _get_rest_path("/mlflow/users/<string:username>/registered-models/regex/update")
DELETE_USER_REGISTERED_MODEL_REGEX_PERMISSION = _get_rest_path("/mlflow/users/<string:username>/registered-models/regex/delete")

CREATE_USER_PROMPT_REGEX_PERMISSION = _get_rest_path("/mlflow/users/<string:username>/prompts/regex/create")
GET_USER_PROMPT_REGEX_PERMISSION = _get_rest_path("/mlflow/users/<string:username>/prompts/regex")
UPDATE_USER_PROMPT_REGEX_PERMISSION = _get_rest_path("/mlflow/users/<string:username>/prompts/regex/update")
DELETE_USER_PROMPT_REGEX_PERMISSION = _get_rest_path("/mlflow/users/<string:username>/prompts/regex/delete")

# manage group permissions
GET_GROUPS = _get_rest_path("/mlflow/groups")
GET_GROUP_USERS = _get_rest_path("/mlflow/groups/<string:group_name>/users")

CREATE_GROUP_EXPERIMENT_PERMISSION = _get_rest_path("/mlflow/groups/<string:group_name>/experiments/create")
GET_GROUP_EXPERIMENTS_PERMISSION = _get_rest_path("/mlflow/groups/<string:group_name>/experiments")
UPDATE_GROUP_EXPERIMENT_PERMISSION = _get_rest_path("/mlflow/groups/<string:group_name>/experiments/update")
DELETE_GROUP_EXPERIMENT_PERMISSION = _get_rest_path("/mlflow/groups/<string:group_name>/experiments/delete")

CREATE_GROUP_MODEL_PERMISSION = _get_rest_path("/mlflow/groups/<string:group_name>/registered-models/create")
GET_GROUP_MODELS_PERMISSION = _get_rest_path("/mlflow/groups/<string:group_name>/registered-models")
UPDATE_GROUP_MODEL_PERMISSION = _get_rest_path("/mlflow/groups/<string:group_name>/registered-models/update")
DELETE_GROUP_MODEL_PERMISSION = _get_rest_path("/mlflow/groups/<string:group_name>/registered-models/delete")

CREATE_GROUP_PROMPT_PERMISSION = _get_rest_path("/mlflow/groups/<string:group_name>/prompts/create")
GET_GROUP_PROMPTS_PERMISSION = _get_rest_path("/mlflow/groups/<string:group_name>/prompts")
UPDATE_GROUP_PROMPT_PERMISSION = _get_rest_path("/mlflow/groups/<string:group_name>/prompts/update")
DELETE_GROUP_PROMPT_PERMISSION = _get_rest_path("/mlflow/groups/<string:group_name>/prompts/delete")

CREATE_GROUP_EXPERIMENT_REGEX_PERMISSION = _get_rest_path("/mlflow/groups/<string:group_name>/experiments/regex/create")
GET_GROUP_EXPERIMENT_REGEX_PERMISSION = _get_rest_path("/mlflow/groups/<string:group_name>/experiments/regex")
UPDATE_GROUP_EXPERIMENT_REGEX_PERMISSION = _get_rest_path("/mlflow/groups/<string:group_name>/experiments/regex/update")
DELETE_GROUP_EXPERIMENT_REGEX_PERMISSION = _get_rest_path("/mlflow/groups/<string:group_name>/experiments/regex/delete")

CREATE_GROUP_REGISTERED_MODEL_REGEX_PERMISSION = _get_rest_path(
    "/mlflow/groups/<string:group_name>/registered-models/regex/create"
)
GET_GROUP_REGISTERED_MODEL_REGEX_PERMISSION = _get_rest_path("/mlflow/groups/<string:group_name>/registered-models/regex")
UPDATE_GROUP_REGISTERED_MODEL_REGEX_PERMISSION = _get_rest_path(
    "/mlflow/groups/<string:group_name>/registered-models/regex/update"
)
DELETE_GROUP_REGISTERED_MODEL_REGEX_PERMISSION = _get_rest_path(
    "/mlflow/groups/<string:group_name>/registered-models/regex/delete"
)

CREATE_GROUP_PROMPT_REGEX_PERMISSION = _get_rest_path("/mlflow/groups/<string:group_name>/prompts/regex/create")
GET_GROUP_PROMPT_REGEX_PERMISSION = _get_rest_path("/mlflow/groups/<string:group_name>/prompts/regex")
UPDATE_GROUP_PROMPT_REGEX_PERMISSION = _get_rest_path("/mlflow/groups/<string:group_name>/prompts/regex/update")
DELETE_GROUP_PROMPT_REGEX_PERMISSION = _get_rest_path("/mlflow/groups/<string:group_name>/prompts/regex/delete")
