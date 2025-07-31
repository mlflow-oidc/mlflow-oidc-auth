"""
MLflow OIDC Auth Utilities Package

This package provides utility functions for MLflow OIDC authentication,
including data fetching, permission checking, and request handling.
"""

# Import all public functions to maintain backward compatibility
from .data_fetching import (
    fetch_all_registered_models,
    fetch_all_experiments,
    fetch_all_prompts,
    fetch_registered_models_paginated,
    fetch_experiments_paginated,
    fetch_readable_experiments,
    fetch_readable_registered_models,
    fetch_readable_logged_models,
)

from .permissions import (
    effective_experiment_permission,
    effective_registered_model_permission,
    effective_prompt_permission,
    can_read_experiment,
    can_read_registered_model,
    can_manage_experiment,
    can_manage_registered_model,
    get_permission_from_store_or_default,
    _get_registered_model_permission_from_regex,
    _get_experiment_permission_from_regex,
    _get_registered_model_group_permission_from_regex,
    _get_experiment_group_permission_from_regex,
    _permission_prompt_sources_config,
    _permission_experiment_sources_config,
    _permission_registered_model_sources_config,
)

from .request_helpers import (
    get_url_param,
    get_optional_url_param,
    get_request_param,
    get_optional_request_param,
    get_username,
    get_is_admin,
    get_experiment_id,
    get_model_id,
    get_model_name,
    _experiment_id_from_name,
)

from .decorators import (
    check_experiment_permission,
    check_registered_model_permission,
    check_prompt_permission,
    check_admin_permission,
)

from .uri_helpers import (
    get_configured_or_dynamic_redirect_uri,
    normalize_url_port,
)

# Export everything for backward compatibility
__all__ = [
    # Data fetching
    "fetch_all_registered_models",
    "fetch_all_experiments",
    "fetch_all_prompts",
    "fetch_registered_models_paginated",
    "fetch_experiments_paginated",
    "fetch_readable_experiments",
    "fetch_readable_registered_models",
    "fetch_readable_logged_models",
    # Permissions
    "effective_experiment_permission",
    "effective_registered_model_permission",
    "effective_prompt_permission",
    "can_read_experiment",
    "can_read_registered_model",
    "can_manage_experiment",
    "can_manage_registered_model",
    "get_permission_from_store_or_default",
    "_get_registered_model_permission_from_regex",
    "_get_experiment_permission_from_regex",
    "_get_registered_model_group_permission_from_regex",
    "_get_experiment_group_permission_from_regex",
    "_permission_prompt_sources_config",
    "_permission_experiment_sources_config",
    "_permission_registered_model_sources_config",
    # Request helpers
    "get_url_param",
    "get_optional_url_param",
    "get_request_param",
    "get_optional_request_param",
    "get_username",
    "get_is_admin",
    "get_experiment_id",
    "get_model_id",
    "get_model_name",
    "_experiment_id_from_name",
    # Decorators
    "check_experiment_permission",
    "check_registered_model_permission",
    "check_prompt_permission",
    "check_admin_permission",
    # URI utilities
    "get_configured_or_dynamic_redirect_uri",
    "normalize_url_port",
]
