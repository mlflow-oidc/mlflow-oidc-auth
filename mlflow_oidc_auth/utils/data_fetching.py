"""
Data fetching utilities for MLflow resources.

This module provides functions to fetch experiments, registered models, logged models,
and gateway endpoints from MLflow stores with proper pagination and permission filtering.
All functions handle pagination automatically to ensure complete data retrieval.

Key Features:
- Automatic pagination handling for large datasets
- Permission-based filtering for security
- Support for both complete and paginated data retrieval
- Efficient memory usage through streaming pagination
- Gateway endpoint fetching from MLflow's unified gateway
"""

from typing import Any, Dict, List, Optional

from mlflow.entities import Experiment
from mlflow.entities.model_registry import RegisteredModel
from mlflow.server.handlers import _get_model_registry_store, _get_tracking_store
from mlflow.store.entities.paged_list import PagedList

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.permissions import get_permission
from mlflow_oidc_auth.store import store
from mlflow_oidc_auth.utils.permissions import can_read_experiment, can_read_registered_model


def fetch_all_registered_models(
    filter_string: Optional[str] = None, order_by: Optional[List[str]] = None, max_results_per_page: int = 1000
) -> List[RegisteredModel]:
    """
    Fetch ALL registered models from the MLflow model registry using pagination.
    This ensures we get all models, not just the first page.

    Args:
        filter_string: Filter string for the search
        order_by: List of order by clauses
        max_results_per_page: Maximum number of results to fetch per page (default: 1000)

    Returns:
        List of ALL RegisteredModel objects
    """
    all_models = []
    page_token = None

    while True:
        result = _get_model_registry_store().search_registered_models(
            filter_string=filter_string, max_results=max_results_per_page, order_by=order_by, page_token=page_token
        )

        all_models.extend(result)

        # Check if there are more pages
        if hasattr(result, "token") and result.token:
            page_token = result.token
        else:
            break

    return all_models


def fetch_all_experiments(
    view_type: int = 1, max_results_per_page: int = 1000, order_by: Optional[List[str]] = None, filter_string: Optional[str] = None  # ACTIVE_ONLY
) -> List[Experiment]:
    """
    Fetch ALL experiments from the MLflow tracking store using pagination.
    This ensures we get all experiments, not just the first page.

    Args:
        view_type: ViewType for experiments (1=ACTIVE_ONLY, 2=DELETED_ONLY, 3=ALL)
        max_results_per_page: Maximum number of results to fetch per page (default: 1000)
        order_by: List of order by clauses
        filter_string: Filter string for the search

    Returns:
        List of ALL Experiment objects
    """
    all_experiments = []
    page_token = None

    while True:
        result = _get_tracking_store().search_experiments(
            view_type=view_type,
            max_results=max_results_per_page,
            order_by=order_by,
            filter_string=filter_string,
            page_token=page_token,
        )

        all_experiments.extend(result)

        # Check if there are more pages
        if hasattr(result, "token") and result.token:
            page_token = result.token
        else:
            break

    return all_experiments


def fetch_all_prompts(max_results_per_page: int = 1000) -> List[RegisteredModel]:
    """
    Fetch ALL registered models that are marked as prompts using pagination.
    This ensures we get all prompts, not just the first page.

    Args:
        max_results_per_page: Maximum number of results to fetch per page (default: 1000)

    Returns:
        List of ALL RegisteredModel objects that are prompts
    """
    filter_string = "tags.`mlflow.prompt.is_prompt` = 'true'"
    return fetch_all_registered_models(filter_string=filter_string, max_results_per_page=max_results_per_page)


def fetch_registered_models_paginated(
    filter_string: Optional[str] = None, max_results: int = 1000, order_by: Optional[List[str]] = None, page_token=None
) -> PagedList[RegisteredModel]:
    """
    Fetch registered models with pagination support.

    Args:
        filter_string: Filter string for the search
        max_results: Maximum number of results to return
        order_by: List of order by clauses
        page_token: Token for pagination

    Returns:
        PagedList of RegisteredModel objects
    """
    return _get_model_registry_store().search_registered_models(
        filter_string=filter_string,
        max_results=max_results,
        order_by=order_by,
        page_token=page_token,
    )


def fetch_experiments_paginated(
    view_type: int = 1,
    max_results: int = 1000,
    order_by: Optional[List[str]] = None,
    filter_string: Optional[str] = None,
    page_token=None,  # ACTIVE_ONLY
) -> PagedList[Experiment]:
    """
    Fetch experiments with pagination support.

    Args:
        view_type: ViewType for experiments (1=ACTIVE_ONLY, 2=DELETED_ONLY, 3=ALL)
        max_results: Maximum number of results to return
        order_by: List of order by clauses
        filter_string: Filter string for the search
        page_token: Token for pagination

    Returns:
        PagedList of Experiment objects
    """
    return _get_tracking_store().search_experiments(
        view_type=view_type,
        max_results=max_results,
        order_by=order_by,
        filter_string=filter_string,
        page_token=page_token,
    )


def fetch_readable_experiments(
    username: str,
    view_type: int = 1,
    max_results_per_page: int = 1000,
    order_by: Optional[List[str]] = None,
    filter_string: Optional[str] = None,
) -> List[Experiment]:
    """
    Fetch ALL experiments that the user can read from the MLflow tracking store using pagination.
    This ensures we get all readable experiments, not just the first page.

    Args:
        view_type: ViewType for experiments (1=ACTIVE_ONLY, 2=DELETED_ONLY, 3=ALL)
        max_results_per_page: Maximum number of results to fetch per page (default: 1000)
        order_by: List of order by clauses
        filter_string: Filter string for the search
        username: Username to check permissions for (defaults to current user)

    Returns:
        List of Experiment objects that the user can read
    """
    # Get all experiments matching the filter
    all_experiments = fetch_all_experiments(view_type=view_type, max_results_per_page=max_results_per_page, order_by=order_by, filter_string=filter_string)

    # Filter by permissions
    readable_experiments = [experiment for experiment in all_experiments if can_read_experiment(experiment.experiment_id, username)]

    return readable_experiments


def fetch_readable_registered_models(
    username: str,
    filter_string: Optional[str] = None,
    order_by: Optional[List[str]] = None,
    max_results_per_page: int = 1000,
) -> List[RegisteredModel]:
    """
    Fetch ALL registered models that the user can read from the MLflow model registry using pagination.
    This ensures we get all readable models, not just the first page.

    Args:
        filter_string: Filter string for the search
        order_by: List of order by clauses
        max_results_per_page: Maximum number of results to fetch per page (default: 1000)
        username: Username to check permissions for (defaults to current user)

    Returns:
        List of RegisteredModel objects that the user can read
    """

    # Get all models matching the filter
    all_models = fetch_all_registered_models(filter_string=filter_string, order_by=order_by, max_results_per_page=max_results_per_page)

    # Filter by permissions
    readable_models = [model for model in all_models if can_read_registered_model(model.name, username)]

    return readable_models


def fetch_readable_logged_models(
    username: str,
    experiment_ids: Optional[List[str]] = None,
    filter_string: Optional[str] = None,
    order_by: Optional[List[dict]] = None,
    max_results_per_page: int = 1000,
) -> List:
    """
    Fetch ALL logged models that the user can read from the MLflow tracking store using pagination.
    This ensures we get all readable logged models, not just the first page.

    Args:
        experiment_ids: List of experiment IDs to search within
        filter_string: Filter string for the search
        order_by: List of order by clauses
        max_results_per_page: Maximum number of results to fetch per page (default: 1000)
        username: Username to check permissions for (defaults to current user)

    Returns:
        List of LoggedModel objects that the user can read
    """

    # Get user permissions
    perms = store.list_experiment_permissions(username)
    can_read_perms = {p.experiment_id: get_permission(p.permission).can_read for p in perms}
    default_can_read = get_permission(config.DEFAULT_MLFLOW_PERMISSION).can_read

    all_models = []
    page_token = None
    tracking_store = _get_tracking_store()

    # Parameters for search
    params = {
        "experiment_ids": experiment_ids or [],
        "filter_string": filter_string,
        "order_by": order_by,
    }

    while True:
        result = tracking_store.search_logged_models(max_results=max_results_per_page, page_token=page_token, **params)

        # Filter models based on read permissions
        for model in result:
            if can_read_perms.get(model.experiment_id, default_can_read):
                all_models.append(model)

        # Check if there are more pages
        if hasattr(result, "token") and result.token:
            page_token = result.token
        else:
            break

    return all_models


def fetch_all_gateway_endpoints() -> List[Dict[str, Any]]:
    """
    Fetch ALL gateway endpoints from the MLflow tracking store.

    This function retrieves gateway endpoints from MLflow's unified gateway store,
    which stores endpoint configurations for the AI Gateway.

    Returns:
        List of gateway endpoint dictionaries containing endpoint metadata.
        Each dictionary includes fields like 'endpoint_id', 'name', 'model_mappings', etc.
    """
    all_endpoints: List[Dict[str, Any]] = []

    result = _get_tracking_store().list_gateway_endpoints()

    # Convert endpoint objects to dictionaries if needed
    for endpoint in result:
        if hasattr(endpoint, "to_dict"):
            all_endpoints.append(endpoint.to_dict())
        elif hasattr(endpoint, "__dict__"):
            all_endpoints.append(vars(endpoint))
        else:
            all_endpoints.append(endpoint)

    return all_endpoints


def fetch_all_gateway_secrets() -> List[Dict[str, Any]]:
    """
    Fetch ALL gateway secrets from the MLflow tracking store.

    Returns:
        List of gateway secret dictionaries.
    """
    all_secrets: List[Dict[str, Any]] = []

    # MLflow uses list_secret_infos for gateway secrets
    result = _get_tracking_store().list_secret_infos()

    for secret in result:
        if hasattr(secret, "to_dict"):
            all_secrets.append(secret.to_dict())
        elif hasattr(secret, "__dict__"):
            all_secrets.append(vars(secret))
        else:
            all_secrets.append(secret)

    return all_secrets


def fetch_all_gateway_model_definitions() -> List[Dict[str, Any]]:
    """
    Fetch ALL gateway model definitions from the MLflow tracking store.

    Returns:
        List of gateway model definition dictionaries.
    """
    all_models: List[Dict[str, Any]] = []

    result = _get_tracking_store().list_gateway_model_definitions()

    for model in result:
        if hasattr(model, "to_dict"):
            all_models.append(model.to_dict())
        elif hasattr(model, "__dict__"):
            all_models.append(vars(model))
        else:
            all_models.append(model)

    return all_models
