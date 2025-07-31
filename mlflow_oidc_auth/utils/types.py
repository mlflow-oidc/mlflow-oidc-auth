"""
Type definitions for MLflow OIDC Auth utilities.

This module provides common type definitions used across the MLflow OIDC Auth system.
"""

from typing import NamedTuple
from mlflow_oidc_auth.permissions import Permission


class PermissionResult(NamedTuple):
    """
    Result object containing permission information and its source.

    This class encapsulates both the permission details and metadata about
    where the permission was determined from (e.g., user, group, regex, fallback).

    Attributes:
        permission (Permission): The Permission object containing access rights
        type (str): String indicating the source type (e.g., 'user', 'group', 'regex', 'fallback')
    """

    permission: Permission
    type: str
