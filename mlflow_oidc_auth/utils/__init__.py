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
    fetch_all_gateway_endpoints,
    fetch_all_gateway_secrets,
    fetch_all_gateway_model_definitions,
)

from .permissions import (
    effective_experiment_permission,
    effective_registered_model_permission,
    effective_prompt_permission,
    effective_scorer_permission,
    can_read_experiment,
    can_read_registered_model,
    can_manage_experiment,
    can_manage_registered_model,
    can_manage_scorer,
    get_permission_from_store_or_default,
)

from .request_helpers import (
    get_url_param,
    get_optional_url_param,
    get_request_param,
    get_optional_request_param,
    get_experiment_id,
    get_model_id,
    get_model_name,
    _experiment_id_from_name,
)

from .request_helpers_fastapi import (
    get_username,
    get_is_admin,
    get_base_path,
    is_authenticated,
)


from .uri import (
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
    "fetch_all_gateway_endpoints",
    "fetch_all_gateway_secrets",
    "fetch_all_gateway_model_definitions",
    # Permissions
    "effective_experiment_permission",
    "effective_registered_model_permission",
    "effective_prompt_permission",
    "effective_scorer_permission",
    "can_read_experiment",
    "can_read_registered_model",
    "can_manage_experiment",
    "can_manage_registered_model",
    "can_manage_scorer",
    "get_permission_from_store_or_default",
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
    # URI utilities
    "get_configured_or_dynamic_redirect_uri",
    "normalize_url_port",
    "get_base_path",
    "is_authenticated",
]
