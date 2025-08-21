import os

from flask_caching import Cache
from flask_session import Session
from mlflow.server import app
from werkzeug.middleware.proxy_fix import ProxyFix

from mlflow_oidc_auth import routes, views
from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.hooks import after_request_hook, before_request_hook
from mlflow_oidc_auth.logger import get_logger

logger = get_logger()

# Configure custom Flask app
template_dir = os.path.dirname(__file__)
template_dir = os.path.join(template_dir, "templates")

app.config.from_object(config)
app.secret_key = app.config["SECRET_KEY"].encode("utf8")
app.template_folder = template_dir
static_folder = app.static_folder

# Configure ProxyFix middleware to handle reverse proxy headers
app.wsgi_app = ProxyFix(
    app.wsgi_app,
    x_for=config.PROXY_FIX_X_FOR,
    x_proto=config.PROXY_FIX_X_PROTO,
    x_host=config.PROXY_FIX_X_HOST,
    x_port=config.PROXY_FIX_X_PORT,
    x_prefix=config.PROXY_FIX_X_PREFIX,
)

logger.debug(
    f"ProxyFix middleware configured - x_for={config.PROXY_FIX_X_FOR}, x_proto={config.PROXY_FIX_X_PROTO}, x_host={config.PROXY_FIX_X_HOST}, x_port={config.PROXY_FIX_X_PORT}, x_prefix={config.PROXY_FIX_X_PREFIX}"
)

# Add links to MLFlow UI
if config.EXTEND_MLFLOW_MENU:
    app.view_functions["serve"] = views.index

# OIDC routes
app.add_url_rule(rule=routes.LOGIN, methods=["GET"], view_func=views.login)
app.add_url_rule(rule=routes.LOGOUT, methods=["GET"], view_func=views.logout)
app.add_url_rule(rule=routes.CALLBACK, methods=["GET"], view_func=views.callback)

# UI routes
app.add_url_rule(rule=routes.STATIC, methods=["GET"], view_func=views.oidc_static)
app.add_url_rule(rule=routes.UI, methods=["GET"], view_func=views.oidc_ui)
app.add_url_rule(rule=routes.UI_ROOT, methods=["GET"], view_func=views.oidc_ui)

# Runtime configuration endpoint under UI path
app.add_url_rule(rule=routes.UI_CONFIG, methods=["GET"], view_func=views.get_runtime_config)

# User token
app.add_url_rule(rule=routes.CREATE_ACCESS_TOKEN, methods=["PATCH"], view_func=views.create_user_access_token)
app.add_url_rule(rule=routes.GET_CURRENT_USER, methods=["GET"], view_func=views.get_current_user)

# User management
app.add_url_rule(rule=routes.CREATE_USER, methods=["POST"], view_func=views.create_new_user)
app.add_url_rule(rule=routes.GET_USER, methods=["GET"], view_func=views.get_user)
app.add_url_rule(rule=routes.UPDATE_USER_PASSWORD, methods=["PATCH"], view_func=views.update_username_password)
app.add_url_rule(rule=routes.UPDATE_USER_ADMIN, methods=["PATCH"], view_func=views.update_user_admin)
app.add_url_rule(rule=routes.DELETE_USER, methods=["DELETE"], view_func=views.delete_user)


# UI routes support
app.add_url_rule(rule=routes.EXPERIMENT_USER_PERMISSIONS, methods=["GET"], view_func=views.get_experiment_users)
app.add_url_rule(rule=routes.PROMPT_USER_PERMISSIONS, methods=["GET"], view_func=views.get_prompt_users)
app.add_url_rule(rule=routes.REGISTERED_MODEL_USER_PERMISSIONS, methods=["GET"], view_func=views.get_registered_model_users)

# List resources
app.add_url_rule(rule=routes.LIST_EXPERIMENTS, methods=["GET"], view_func=views.list_experiments)
app.add_url_rule(rule=routes.LIST_MODELS, methods=["GET"], view_func=views.list_registered_models)
app.add_url_rule(rule=routes.LIST_PROMPTS, methods=["GET"], view_func=views.list_prompts)
app.add_url_rule(rule=routes.LIST_USERS, methods=["GET"], view_func=views.list_users)
app.add_url_rule(rule=routes.LIST_GROUPS, methods=["GET"], view_func=views.list_groups)

# user experiment permission management
app.add_url_rule(rule=routes.USER_EXPERIMENT_PERMISSIONS, methods=["GET"], view_func=views.list_user_experiments)
app.add_url_rule(rule=routes.USER_EXPERIMENT_PERMISSION_DETAIL, methods=["POST"], view_func=views.create_experiment_permission)
app.add_url_rule(rule=routes.USER_EXPERIMENT_PERMISSION_DETAIL, methods=["GET"], view_func=views.get_experiment_permission)
app.add_url_rule(rule=routes.USER_EXPERIMENT_PERMISSION_DETAIL, methods=["PATCH"], view_func=views.update_experiment_permission)
app.add_url_rule(rule=routes.USER_EXPERIMENT_PERMISSION_DETAIL, methods=["DELETE"], view_func=views.delete_experiment_permission)

# user experiment regex permission management
app.add_url_rule(rule=routes.USER_EXPERIMENT_PATTERN_PERMISSIONS, methods=["POST"], view_func=views.create_experiment_regex_permission)
app.add_url_rule(rule=routes.USER_EXPERIMENT_PATTERN_PERMISSIONS, methods=["GET"], view_func=views.list_user_experiment_regex_permission)
app.add_url_rule(rule=routes.USER_EXPERIMENT_PATTERN_PERMISSION_DETAIL, methods=["GET"], view_func=views.get_experiment_regex_permission)
app.add_url_rule(rule=routes.USER_EXPERIMENT_PATTERN_PERMISSION_DETAIL, methods=["PATCH"], view_func=views.update_experiment_regex_permission)
app.add_url_rule(
    rule=routes.USER_EXPERIMENT_PATTERN_PERMISSION_DETAIL,
    methods=["DELETE"],
    view_func=views.delete_experiment_regex_permission,
)

# user prompt management
app.add_url_rule(rule=routes.USER_PROMPT_PERMISSIONS, methods=["GET"], view_func=views.list_user_prompts)
app.add_url_rule(rule=routes.USER_PROMPT_PERMISSION_DETAIL, methods=["POST"], view_func=views.create_prompt_permission)
app.add_url_rule(rule=routes.USER_PROMPT_PERMISSION_DETAIL, methods=["GET"], view_func=views.get_prompt_permission)
app.add_url_rule(rule=routes.USER_PROMPT_PERMISSION_DETAIL, methods=["PATCH"], view_func=views.update_prompt_permission)
app.add_url_rule(rule=routes.USER_PROMPT_PERMISSION_DETAIL, methods=["DELETE"], view_func=views.delete_prompt_permission)

# user prompt regex permission management
app.add_url_rule(rule=routes.USER_PROMPT_PATTERN_PERMISSIONS, methods=["GET"], view_func=views.list_prompt_regex_permissions)
app.add_url_rule(rule=routes.USER_PROMPT_PATTERN_PERMISSIONS, methods=["POST"], view_func=views.create_prompt_regex_permission)
app.add_url_rule(rule=routes.USER_PROMPT_PATTERN_PERMISSION_DETAIL, methods=["GET"], view_func=views.get_prompt_regex_permission)
app.add_url_rule(rule=routes.USER_PROMPT_PATTERN_PERMISSION_DETAIL, methods=["PATCH"], view_func=views.update_prompt_regex_permission)
app.add_url_rule(rule=routes.USER_PROMPT_PATTERN_PERMISSION_DETAIL, methods=["DELETE"], view_func=views.delete_prompt_regex_permission)

# user registered model management
app.add_url_rule(rule=routes.USER_REGISTERED_MODEL_PERMISSIONS, methods=["GET"], view_func=views.list_user_models)
app.add_url_rule(rule=routes.USER_REGISTERED_MODEL_PERMISSION_DETAIL, methods=["POST"], view_func=views.create_registered_model_permission)
app.add_url_rule(rule=routes.USER_REGISTERED_MODEL_PERMISSION_DETAIL, methods=["GET"], view_func=views.get_registered_model_permission)
app.add_url_rule(rule=routes.USER_REGISTERED_MODEL_PERMISSION_DETAIL, methods=["PATCH"], view_func=views.update_registered_model_permission)
app.add_url_rule(rule=routes.USER_REGISTERED_MODEL_PERMISSION_DETAIL, methods=["DELETE"], view_func=views.delete_registered_model_permission)

# user registered model regex permission management
app.add_url_rule(rule=routes.USER_REGISTERED_MODEL_PATTERN_PERMISSIONS, methods=["GET"], view_func=views.list_registered_model_regex_permissions)
app.add_url_rule(rule=routes.USER_REGISTERED_MODEL_PATTERN_PERMISSIONS, methods=["POST"], view_func=views.create_registered_model_regex_permission)
app.add_url_rule(rule=routes.USER_REGISTERED_MODEL_PATTERN_PERMISSION_DETAIL, methods=["GET"], view_func=views.get_registered_model_regex_permission)
app.add_url_rule(rule=routes.USER_REGISTERED_MODEL_PATTERN_PERMISSION_DETAIL, methods=["PATCH"], view_func=views.update_registered_model_regex_permission)
app.add_url_rule(rule=routes.USER_REGISTERED_MODEL_PATTERN_PERMISSION_DETAIL, methods=["DELETE"], view_func=views.delete_registered_model_regex_permission)

app.add_url_rule(rule=routes.GROUP_USER_PERMISSIONS, methods=["GET"], view_func=views.get_group_users)

app.add_url_rule(rule=routes.GROUP_EXPERIMENT_PERMISSIONS, methods=["GET"], view_func=views.list_group_experiments)
app.add_url_rule(rule=routes.GROUP_EXPERIMENT_PERMISSION_DETAIL, methods=["POST"], view_func=views.create_group_experiment_permission)
app.add_url_rule(rule=routes.GROUP_EXPERIMENT_PERMISSION_DETAIL, methods=["DELETE"], view_func=views.delete_group_experiment_permission)
app.add_url_rule(rule=routes.GROUP_EXPERIMENT_PERMISSION_DETAIL, methods=["PATCH"], view_func=views.update_group_experiment_permission)

app.add_url_rule(rule=routes.GROUP_REGISTERED_MODEL_PERMISSIONS, methods=["GET"], view_func=views.list_group_models)
app.add_url_rule(rule=routes.GROUP_REGISTERED_MODEL_PERMISSION_DETAIL, methods=["POST"], view_func=views.create_group_model_permission)
app.add_url_rule(rule=routes.GROUP_REGISTERED_MODEL_PERMISSION_DETAIL, methods=["DELETE"], view_func=views.delete_group_model_permission)
app.add_url_rule(rule=routes.GROUP_REGISTERED_MODEL_PERMISSION_DETAIL, methods=["PATCH"], view_func=views.update_group_model_permission)

app.add_url_rule(rule=routes.GROUP_PROMPT_PERMISSIONS, methods=["GET"], view_func=views.get_group_prompts)
app.add_url_rule(rule=routes.GROUP_PROMPT_PERMISSION_DETAIL, methods=["POST"], view_func=views.create_group_prompt_permission)
app.add_url_rule(rule=routes.GROUP_PROMPT_PERMISSION_DETAIL, methods=["DELETE"], view_func=views.delete_group_prompt_permission)
app.add_url_rule(rule=routes.GROUP_PROMPT_PERMISSION_DETAIL, methods=["PATCH"], view_func=views.update_group_prompt_permission)

app.add_url_rule(rule=routes.GROUP_EXPERIMENT_PATTERN_PERMISSIONS, methods=["GET"], view_func=views.list_group_experiment_regex_permissions)
app.add_url_rule(rule=routes.GROUP_EXPERIMENT_PATTERN_PERMISSIONS, methods=["POST"], view_func=views.create_group_experiment_regex_permission)
app.add_url_rule(rule=routes.GROUP_EXPERIMENT_PATTERN_PERMISSION_DETAIL, methods=["GET"], view_func=views.get_group_experiment_regex_permission)
app.add_url_rule(
    rule=routes.GROUP_EXPERIMENT_PATTERN_PERMISSION_DETAIL,
    methods=["PATCH"],
    view_func=views.update_group_experiment_regex_permission,
)
app.add_url_rule(
    rule=routes.GROUP_EXPERIMENT_PATTERN_PERMISSION_DETAIL,
    methods=["DELETE"],
    view_func=views.delete_group_experiment_regex_permission,
)

app.add_url_rule(
    rule=routes.GROUP_REGISTERED_MODEL_PATTERN_PERMISSIONS,
    methods=["POST"],
    view_func=views.create_group_registered_model_regex_permission,
)
app.add_url_rule(
    rule=routes.GROUP_REGISTERED_MODEL_PATTERN_PERMISSIONS,
    methods=["GET"],
    view_func=views.list_group_registered_model_regex_permissions,
)
app.add_url_rule(
    rule=routes.GROUP_REGISTERED_MODEL_PATTERN_PERMISSION_DETAIL,
    methods=["GET"],
    view_func=views.get_group_registered_model_regex_permission,
)
app.add_url_rule(
    rule=routes.GROUP_REGISTERED_MODEL_PATTERN_PERMISSION_DETAIL,
    methods=["PATCH"],
    view_func=views.update_group_registered_model_regex_permission,
)
app.add_url_rule(
    rule=routes.GROUP_REGISTERED_MODEL_PATTERN_PERMISSION_DETAIL,
    methods=["DELETE"],
    view_func=views.delete_group_registered_model_regex_permission,
)

app.add_url_rule(rule=routes.GROUP_PROMPT_PATTERN_PERMISSIONS, methods=["GET"], view_func=views.list_group_prompt_regex_permissions)
app.add_url_rule(rule=routes.GROUP_PROMPT_PATTERN_PERMISSIONS, methods=["POST"], view_func=views.create_group_prompt_regex_permission)
app.add_url_rule(rule=routes.GROUP_PROMPT_PATTERN_PERMISSION_DETAIL, methods=["GET"], view_func=views.get_group_prompt_regex_permission)
app.add_url_rule(rule=routes.GROUP_PROMPT_PATTERN_PERMISSION_DETAIL, methods=["PATCH"], view_func=views.update_group_prompt_regex_permission)
app.add_url_rule(rule=routes.GROUP_PROMPT_PATTERN_PERMISSION_DETAIL, methods=["DELETE"], view_func=views.delete_group_prompt_regex_permission)
###############################


# Add new hooks
app.before_request(before_request_hook)
app.after_request(after_request_hook)

# Set up session
Session(app)
cache = Cache(app)
