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
    get_run_experiment_id,
)

from .permissions import (
    effective_experiment_permission,
    effective_new_experiment_permission,
    effective_new_registered_model_permission,
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
    get_request_param_values,
    get_experiment_ids,
    get_model_ids,
    get_model_names,
    all_source_values,
    request_body_dict,
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

from .oidc_field_extraction import (
    extract_field_from_payload,
    extract_username,
    extract_display_name,
)

from .group_detection import (
    call_group_detection_plugin,
)
from .group_name import (
    MAX_GROUP_NAME_LENGTH,
    GROUP_NAME_RESERVED_CHARS,
    validate_group_name_chars,
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
    "get_run_experiment_id",
    # Permissions
    "effective_experiment_permission",
    "effective_new_experiment_permission",
    "effective_new_registered_model_permission",
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
    "get_request_param_values",
    "get_experiment_ids",
    "get_model_ids",
    "get_model_names",
    "all_source_values",
    "request_body_dict",
    "_experiment_id_from_name",
    # URI utilities
    "get_configured_or_dynamic_redirect_uri",
    "normalize_url_port",
    "get_base_path",
    "is_authenticated",
    # OIDC field extraction
    "extract_field_from_payload",
    "extract_username",
    "extract_display_name",
    # Group detection plugins
    "call_group_detection_plugin",
    # Group name validation
    "MAX_GROUP_NAME_LENGTH",
    "GROUP_NAME_RESERVED_CHARS",
    "validate_group_name_chars",
]
