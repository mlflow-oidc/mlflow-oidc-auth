"""
OIDC field extraction utilities.

Provides functions to extract user information fields from OIDC userinfo
and token payloads using configurable field names.
"""

from typing import Any, Dict, List, Optional

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.repository.user import normalize_username

logger = get_logger()

# Default and alternate values for the `source` parameter shared by the functions below,
# so every call site describes the payload the same way instead of retyping the string.
OIDC_USERINFO_SOURCE = "OIDC userinfo"
BEARER_TOKEN_SOURCE = "bearer token payload"


def extract_field_from_payload(
    payload: Dict[str, Any],
    field_list: List[str],
    field_type_name: str,
    source: str = OIDC_USERINFO_SOURCE,
) -> tuple[Optional[str], Optional[str]]:
    """
    Extract a field value from a payload using a configured list of field names.

    This function attempts to extract a value from the payload by iterating through
    the configured field names in order and returning the first non-blank value found.
    The value must be a string; non-string values (including non-string falsy values
    like 0 or False) are rejected with an error. A missing, empty, or whitespace-only
    string is treated as absent, so it falls through to the next configured field
    instead of being accepted as the extracted value.

    Parameters:
        payload: Dictionary containing the fields to extract from (e.g., userinfo or token payload)
        field_list: List of field names to try in order
        field_type_name: Name of the field type (e.g., "username", "display_name")
        source: Human-readable description of the payload, used in the "not found" error
            message (e.g. "OIDC userinfo", "bearer token payload")

    Returns:
        Tuple of (value, error_message) where:
        - value is the extracted string value or None if not found/invalid
        - error_message is an error string if extraction failed, None if successful
    """
    field_label = field_type_name.replace("_", " ")

    if not field_list:
        return None, f"No {field_label} fields configured"

    for field in field_list:
        value = payload.get(field)
        if value is None:
            continue
        if not isinstance(value, str):
            error_msg = f"Invalid OIDC {field_label} field: {field} is not a string"
            logger.error(error_msg)
            return None, error_msg
        if value.strip():
            return value, None
        # Empty or whitespace-only string: treat as absent, try the next configured field.

    # No field found (or every configured field was missing/blank)
    return None, f"No {field_label} provided in {source}"


def extract_username(payload: Dict[str, Any], source: str = OIDC_USERINFO_SOURCE) -> tuple[Optional[str], Optional[str]]:
    """
    Extract username from OIDC userinfo or token payload.

    Uses configured OIDC_USERNAME_FIELD list to determine which fields to check.

    Parameters:
        payload: OIDC userinfo or token payload dictionary
        source: Human-readable description of the payload, used in the "not found" error message

    Returns:
        Tuple of (username, error_message) where:
        - username is the extracted username (normalized to its canonical case) or None if not found/invalid
        - error_message is an error string if extraction failed, None if successful
    """
    value, error_msg = extract_field_from_payload(payload, config.OIDC_USERNAME_FIELD, "username", source=source)
    if error_msg:
        return None, error_msg
    return normalize_username(value), None


def extract_display_name(payload: Dict[str, Any], source: str = OIDC_USERINFO_SOURCE) -> tuple[Optional[str], Optional[str]]:
    """
    Extract display name from OIDC userinfo or token payload.

    Uses configured OIDC_DISPLAY_NAME_FIELD list to determine which fields to check.

    Parameters:
        payload: OIDC userinfo or token payload dictionary
        source: Human-readable description of the payload, used in the "not found" error message

    Returns:
        Tuple of (display_name, error_message) where:
        - display_name is the extracted display name or None if not found/invalid
        - error_message is an error string if extraction failed, None if successful
    """
    return extract_field_from_payload(payload, config.OIDC_DISPLAY_NAME_FIELD, "display_name", source=source)
