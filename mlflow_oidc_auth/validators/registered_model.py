import re

from flask import request
from mlflow.server.handlers import _get_model_registry_store

from mlflow_oidc_auth.permissions import Permission
from mlflow_oidc_auth.utils import (
    effective_registered_model_permission,
    effective_experiment_permission,
    get_model_name,
    get_model_id,
    get_request_param,
)
from mlflow.server.handlers import _get_tracking_store


_PROMPT_TAG = "mlflow.prompt.is_prompt"
_PROMPT_EXPERIMENT_IDS_TAG = "_mlflow_experiment_ids"


def _coerce_tags_to_map(tags) -> dict[str, str]:
    if isinstance(tags, dict):
        return {str(k): str(v) for k, v in tags.items()}
    out: dict[str, str] = {}
    for tag in tags or []:
        if isinstance(tag, dict):
            key = tag.get("key")
            value = tag.get("value")
        else:
            key = getattr(tag, "key", None)
            value = getattr(tag, "value", None)
        if key is not None and value is not None:
            out[str(key)] = str(value)
    return out


def _extract_experiment_ids_from_text(value: str | None) -> list[str]:
    if not value:
        return []
    return re.findall(r"\d+", str(value))


def _is_prompt_tags(tags_map: dict[str, str]) -> bool:
    return tags_map.get(_PROMPT_TAG, "").strip().lower() == "true"


def _get_prompt_experiment_ids_from_tags(tags_map: dict[str, str]) -> list[str]:
    return _extract_experiment_ids_from_text(tags_map.get(_PROMPT_EXPERIMENT_IDS_TAG))


def _can_read_prompt_experiment_scope(experiment_ids: list[str], username: str) -> bool:
    if not experiment_ids:
        return False
    for experiment_id in experiment_ids:
        if not effective_experiment_permission(experiment_id, username).permission.can_read:
            return False
    return True


def _can_update_prompt_experiment_scope(experiment_ids: list[str], username: str) -> bool:
    if not experiment_ids:
        return False
    for experiment_id in experiment_ids:
        if not effective_experiment_permission(experiment_id, username).permission.can_update:
            return False
    return True


def _get_registered_model_tags(model_name: str) -> dict[str, str]:
    try:
        model = _get_model_registry_store().get_registered_model(model_name)
    except Exception:
        return {}
    return _coerce_tags_to_map(getattr(model, "tags", None))


def _extract_prompt_context_from_request() -> tuple[bool, list[str]]:
    if request.method in {"POST", "PATCH", "PUT"} and request.is_json:
        data = request.get_json(silent=True) or {}
    else:
        data = {}

    tags_map = _coerce_tags_to_map(data.get("tags", []))
    is_prompt = _is_prompt_tags(tags_map)
    experiment_ids = _get_prompt_experiment_ids_from_tags(tags_map)

    # Some callers also send explicit experiment_id(s) in payload.
    if data.get("experiment_id") is not None:
        experiment_ids.append(str(data["experiment_id"]))
    for experiment_id in data.get("experiment_ids", []) or []:
        experiment_ids.append(str(experiment_id))

    return is_prompt, list(dict.fromkeys(experiment_ids))


def _get_permission_from_registered_model_name(username: str) -> Permission:
    model_name = get_model_name()
    return effective_registered_model_permission(model_name, username).permission


def _get_permission_from_model_id(username: str) -> Permission:
    # logged model permissions inherit from parent resource (experiment)
    model_id = get_model_id()
    model = _get_tracking_store().get_logged_model(model_id)
    experiment_id = model.experiment_id
    return effective_experiment_permission(experiment_id, username).permission


def _get_permission_from_model_version(username: str) -> Permission:
    """
    Get permission for model version artifacts.
    Model versions inherit permissions from their registered model.
    """
    return _get_permission_from_registered_model_name(username)


def _get_permission_from_trace_request_id(username: str) -> Permission:
    """
    Get permission for trace artifacts.
    Traces inherit permissions from their parent run/experiment.
    """
    request_id = get_request_param("request_id")
    # Get the trace to find its experiment
    trace = _get_tracking_store().get_trace_info(request_id)
    experiment_id = trace.experiment_id

    return effective_experiment_permission(experiment_id, username).permission


def validate_can_read_registered_model(username: str) -> bool:
    if not _get_permission_from_registered_model_name(username).can_read:
        return False
    model_name = get_model_name()
    tags_map = _get_registered_model_tags(model_name)
    if _is_prompt_tags(tags_map):
        experiment_ids = _get_prompt_experiment_ids_from_tags(tags_map)
        return _can_read_prompt_experiment_scope(experiment_ids, username)
    return True


def validate_can_update_registered_model(username: str) -> bool:
    if not _get_permission_from_registered_model_name(username).can_update:
        return False
    model_name = get_model_name()
    tags_map = _get_registered_model_tags(model_name)
    if _is_prompt_tags(tags_map):
        experiment_ids = _get_prompt_experiment_ids_from_tags(tags_map)
        return _can_update_prompt_experiment_scope(experiment_ids, username)
    return True


def validate_can_delete_registered_model(username: str) -> bool:
    return _get_permission_from_registered_model_name(username).can_delete


def validate_can_manage_registered_model(username: str) -> bool:
    return _get_permission_from_registered_model_name(username).can_manage


def validate_can_read_logged_model(username: str) -> bool:
    return _get_permission_from_model_id(username).can_read


def validate_can_update_logged_model(username: str) -> bool:
    return _get_permission_from_model_id(username).can_update


def validate_can_delete_logged_model(username: str) -> bool:
    return _get_permission_from_model_id(username).can_delete


def validate_can_manage_logged_model(username: str) -> bool:
    return _get_permission_from_model_id(username).can_manage


def validate_can_read_model_version_artifact(username: str) -> bool:
    """Checks READ permission on model version artifacts."""
    return _get_permission_from_model_version(username).can_read


def validate_can_read_trace_artifact(username: str) -> bool:
    """Checks READ permission on trace artifacts."""
    return _get_permission_from_trace_request_id(username).can_read


def validate_can_create_registered_model(username: str) -> bool:
    is_prompt, experiment_ids = _extract_prompt_context_from_request()
    if is_prompt:
        return _can_update_prompt_experiment_scope(experiment_ids, username)
    return _get_permission_from_registered_model_name(username).can_update


def validate_can_create_model_version(username: str) -> bool:
    is_prompt, experiment_ids = _extract_prompt_context_from_request()
    if is_prompt:
        if experiment_ids:
            return _can_update_prompt_experiment_scope(experiment_ids, username)
        # If prompt context is not explicit in payload, inherit from parent model tags.
        model_name = get_model_name()
        model_tags = _get_registered_model_tags(model_name)
        return _can_update_prompt_experiment_scope(_get_prompt_experiment_ids_from_tags(model_tags), username)
    return validate_can_update_registered_model(username)


def validate_can_search_model_versions(username: str) -> bool:
    filter_string = request.args.get("filter", "")
    if not filter_string:
        return True

    names = re.findall(r"name\s*=\s*'([^']+)'", filter_string)
    if not names:
        return True

    for name in names:
        if not effective_registered_model_permission(name, username).permission.can_read:
            return False
        tags_map = _get_registered_model_tags(name)
        if _is_prompt_tags(tags_map):
            if not _can_read_prompt_experiment_scope(_get_prompt_experiment_ids_from_tags(tags_map), username):
                return False
    return True
