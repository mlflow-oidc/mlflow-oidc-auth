from functools import wraps
from typing import Callable

from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.responses.client_error import make_forbidden_response
from mlflow_oidc_auth.store import store
from mlflow_oidc_auth.utils.permissions import can_manage_experiment, can_manage_registered_model
from mlflow_oidc_auth.utils.request_helpers import get_experiment_id, get_is_admin, get_model_name, get_username

logger = get_logger()


def check_experiment_permission(f) -> Callable:
    @wraps(f)
    def decorated_function(*args, **kwargs):
        current_user = store.get_user(get_username())
        if not get_is_admin():
            logger.debug(f"Not Admin. Checking permission for {current_user.username}")
            experiment_id = get_experiment_id()
            if not can_manage_experiment(experiment_id, current_user.username):
                logger.warning(f"Change permission denied for {current_user.username} on experiment {experiment_id}")
                return make_forbidden_response()
        logger.debug(f"Change permission granted for {current_user.username}")
        return f(*args, **kwargs)

    return decorated_function


def check_registered_model_permission(f) -> Callable:
    @wraps(f)
    def decorated_function(*args, **kwargs):
        current_user = store.get_user(get_username())
        if not get_is_admin():
            logger.debug(f"Not Admin. Checking permission for {current_user.username}")
            model_name = get_model_name()
            if not can_manage_registered_model(model_name, current_user.username):
                logger.warning(f"Change permission denied for {current_user.username} on model {model_name}")
                return make_forbidden_response()
        logger.debug(f"Permission granted for {current_user.username}")
        return f(*args, **kwargs)

    return decorated_function


def check_prompt_permission(f) -> Callable:
    @wraps(f)
    def decorated_function(*args, **kwargs):
        current_user = store.get_user(get_username())
        if not get_is_admin():
            logger.debug(f"Not Admin. Checking permission for {current_user.username}")
            prompt_name = get_model_name()
            if not can_manage_registered_model(prompt_name, current_user.username):
                logger.warning(f"Change permission denied for {current_user.username} on prompt {prompt_name}")
                return make_forbidden_response()
        logger.debug(f"Permission granted for {current_user.username}")
        return f(*args, **kwargs)

    return decorated_function


def check_admin_permission(f) -> Callable:
    @wraps(f)
    def decorated_function(*args, **kwargs):
        current_user = store.get_user(get_username())
        if not get_is_admin():
            logger.warning(f"Admin permission denied for {current_user.username}")
            return make_forbidden_response()
        logger.debug(f"Admin permission granted for {current_user.username}")
        return f(*args, **kwargs)

    return decorated_function
