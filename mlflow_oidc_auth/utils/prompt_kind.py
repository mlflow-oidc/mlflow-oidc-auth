"""Which permissions decide access to a registered model: its own, or a prompt's (#479).

MLflow stores a prompt as a registered model tagged ``mlflow.prompt.is_prompt = "true"``, and its
versions as model versions. Every prompt call therefore reaches the plugin as a registered-model or
model-version request. Prompt patterns are kept apart from model patterns (exact-name grants are
shared), so the resolver has to follow the target's kind, which only MLflow knows.
"""

from typing import Any, Optional

from mlflow.exceptions import MlflowException
from mlflow.prompt.constants import IS_PROMPT_TAG_KEY
from mlflow.protos.databricks_pb2 import RESOURCE_DOES_NOT_EXIST, ErrorCode

from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.models import PermissionResult

logger = get_logger()

_MEMO = "_mlflow_oidc_prompt_kinds"

# The tag that makes a registered model a prompt. Writing it changes which grants apply, so only an
# admin may set or delete it on an existing model (validators/registered_model.py).
KIND_TAG_KEY = IS_PROMPT_TAG_KEY


def is_prompt_tags(tags: Any) -> bool:
    """Whether a registered model's tags mark it as a prompt, by MLflow's own rule.

    Parameters:
        tags: Tags as a mapping, as MLflow entities hold them, or as ``key``/``value`` pairs, as
            request bodies and protos carry them.

    Returns:
        True when ``mlflow.prompt.is_prompt`` is ``"true"`` (any case).
    """
    if isinstance(tags, dict):
        value = tags.get(IS_PROMPT_TAG_KEY)
    else:
        value = None
        for tag in tags or ():
            key = tag.get("key") if isinstance(tag, dict) else getattr(tag, "key", None)
            if key == IS_PROMPT_TAG_KEY:
                value = tag.get("value") if isinstance(tag, dict) else getattr(tag, "value", None)
    return str(value or "").lower() == "true"


def _memo() -> Optional[dict]:
    """The request's name-to-kind memo, or None outside a request."""
    from flask import g, has_request_context

    if not has_request_context():
        return None
    memo = getattr(g, _MEMO, None)
    if memo is None:
        memo = {}
        setattr(g, _MEMO, memo)
    return memo


def remember_kind(name: str, is_prompt: bool) -> None:
    """Record a registered model's kind for the rest of the request, from data already at hand.

    Parameters:
        name: The registered model's name.
        is_prompt: Whether it is a prompt.
    """
    memo = _memo()
    if memo is not None:
        memo[name] = is_prompt


def is_prompt(name: str) -> bool:
    """Whether the registered model ``name`` is a prompt.

    Looked up in MLflow's model registry at most once per name per request. A name MLflow does not
    know is not a prompt: nothing can be read or changed through it, and creating it is decided by
    the request's own tags (:func:`request_creates_prompt`).

    Parameters:
        name: The registered model's name.

    Returns:
        True when the model is a prompt.

    Raises:
        MlflowException: Any registry error other than the model not existing. Callers deny: the
            kind decides which grants apply, so an unknown kind must never fall through to one.
    """
    memo = _memo()
    if memo is not None and name in memo:
        return memo[name]
    from mlflow.server.handlers import _get_model_registry_store

    try:
        kind = is_prompt_tags(_get_model_registry_store().get_registered_model(name=name).tags)
    except MlflowException as exc:
        if exc.error_code != ErrorCode.Name(RESOURCE_DOES_NOT_EXIST):
            raise
        kind = False
    if memo is not None:
        memo[name] = kind
    return kind


def request_creates_prompt() -> bool:
    """Whether the current create request makes a prompt (or prompt version), by its own tags.

    MLflow decides the same way (``handlers._is_prompt_request``): at creation the model may not
    exist yet, so its tags cannot be looked up.

    Returns:
        True when the request body carries ``mlflow.prompt.is_prompt = "true"``.
    """
    from mlflow_oidc_auth.utils import request_body_dict

    return is_prompt_tags((request_body_dict() or {}).get("tags"))


def effective_registry_permission(name: str, user: str, *, prompt: Optional[bool] = None) -> PermissionResult:
    """A user's permission on a registered model, resolved as a prompt when it is one.

    Parameters:
        name: The registered model's name.
        user: The username.
        prompt: The model's kind when the caller already knows it; looked up otherwise.

    Returns:
        The effective permission: :func:`effective_prompt_permission` for a prompt,
        :func:`effective_registered_model_permission` otherwise. ``NO_PERMISSIONS`` when the kind
        cannot be determined: it decides which grants apply, so neither set may be guessed.
    """
    from mlflow_oidc_auth.permissions import NO_PERMISSIONS
    from mlflow_oidc_auth.utils.permissions import effective_prompt_permission, effective_registered_model_permission

    if prompt is None:
        try:
            prompt = is_prompt(name)
        except MlflowException as exc:
            # The name is request input: log the error kind, never the name.
            logger.warning("Denying a registry request: the model's kind could not be determined (%s)", exc.error_code)
            return PermissionResult(NO_PERMISSIONS, "kind-unknown")
    return effective_prompt_permission(name, user) if prompt else effective_registered_model_permission(name, user)

