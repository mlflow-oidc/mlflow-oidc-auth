"""
OIDC field extraction utilities.

Provides functions to extract user information fields from OIDC userinfo
and token payloads using configurable field names.
"""

from typing import Any, Dict, List, Optional

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.logger import get_logger

logger = get_logger()


def extract_field_from_payload(
    payload: Dict[str, Any],
    field_list: List[str],
    field_type_name: str,
) -> tuple[Optional[str], Optional[str]]:
    """
    Extract a field value from a payload using a configured list of field names.

    This function attempts to extract a value from the payload by iterating through
    the configured field names in order and returning the first non-None value found.
    The value must be a string; non-string values are rejected with an error.

    Parameters:
        payload: Dictionary containing the fields to extract from (e.g., userinfo or token payload)
        field_list: List of field names to try in order
        field_type_name: Human-readable name of the field type (e.g., "username", "display_name")

    Returns:
        Tuple of (value, error_message) where:
        - value is the extracted string value or None if not found/invalid
        - error_message is an error string if extraction failed, None if successful
    """
    if not field_list:
        return None, f"No {field_type_name} fields configured"

    for field in field_list:
        value = payload.get(field)
        if value is not None:
            if not isinstance(value, str):
                error_msg = f"Invalid OIDC {field_type_name} field: {field} is not a string"
                logger.error(error_msg)
                return None, error_msg
            return value, None

    # No field found
    return None, f"No {field_type_name} provided in OIDC userinfo"


def extract_username(payload: Dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    """
    Extract username from OIDC userinfo or token payload.

    Uses configured OIDC_USERNAME_FIELD list to determine which fields to check.

    Parameters:
        payload: OIDC userinfo or token payload dictionary

    Returns:
        Tuple of (username, error_message) where:
        - username is the extracted username (lowercased) or None if not found/invalid
        - error_message is an error string if extraction failed, None if successful
    """
    value, error_msg = extract_field_from_payload(payload, config.OIDC_USERNAME_FIELD, "username")
    if error_msg:
        return None, error_msg
    return value.lower() if value else None, None


def extract_display_name(payload: Dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    """
    Extract display name from OIDC userinfo or token payload.

    Uses configured OIDC_DISPLAY_NAME_FIELD list to determine which fields to check.

    Parameters:
        payload: OIDC userinfo or token payload dictionary

    Returns:
        Tuple of (display_name, error_message) where:
        - display_name is the extracted display name or None if not found/invalid
        - error_message is an error string if extraction failed, None if successful
    """
    value, error_msg = extract_field_from_payload(payload, config.OIDC_DISPLAY_NAME_FIELD, "display_name")
    return value, error_msg

