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


def is_prompt_row(row: Any) -> bool:
    """Whether a registered model, as an MLflow entity or a proto, is a prompt.

    An entity's public ``tags`` hides ``mlflow.prompt.is_prompt`` (MLflow treats it as internal), so
    an entity is asked through MLflow's own ``_is_prompt()``. A proto, or anything else carrying a
    tag list, still holds the tag and is read with :func:`is_prompt_tags`.

    Parameters:
        row: A ``mlflow.entities.model_registry.RegisteredModel`` or a ``RegisteredModel`` proto.

    Returns:
        True when the row is a prompt.
    """
    from mlflow.entities.model_registry import RegisteredModel

    if isinstance(row, RegisteredModel):
        return row._is_prompt()
    return is_prompt_tags(getattr(row, "tags", None))


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
        kind = is_prompt_row(_get_model_registry_store().get_registered_model(name=name))
    except MlflowException as exc:
        if exc.error_code != ErrorCode.Name(RESOURCE_DOES_NOT_EXIST):
            raise
        kind = False
    if memo is not None:
        memo[name] = kind
    return kind


def prompt_names() -> set:
    """The names of every prompt MLflow serves in the request's workspace, read once per request.

    One registry query instead of a lookup per name, for listings that judge many grant rows. MLflow
    selects the prompts with its own tag filter, so the set agrees with how MLflow classifies them.

    Returns:
        The prompt names.

    Raises:
        MlflowException: A registry error; callers deny.
    """
    from flask import g, has_request_context

    from mlflow_oidc_auth.utils.data_fetching import fetch_all_prompts

    if has_request_context() and hasattr(g, "_mlflow_oidc_prompt_names"):
        return g._mlflow_oidc_prompt_names
    names = {prompt.name for prompt in fetch_all_prompts()}
    if has_request_context():
        g._mlflow_oidc_prompt_names = names
    return names


def request_has_kind_tag_lookalike() -> bool:
    """Whether a create request carries the kind tag under any spelling but the exact one.

    MySQL and SQL Server compare tag keys ignoring case, so MLflow's own prompt filter would read
    ``MLFLOW.PROMPT.IS_PROMPT`` as the kind tag while :func:`is_prompt_row` and
    :func:`request_creates_prompt` would not. The plugin and MLflow must never disagree on whether a
    model is a prompt, so such a key is refused.

    Returns:
        True when a tag key equals the kind tag only after ignoring case or whitespace.
    """
    from mlflow_oidc_auth.utils import request_body_dict

    wanted = IS_PROMPT_TAG_KEY.casefold()
    for tag in (request_body_dict() or {}).get("tags") or ():
        key = tag.get("key") if isinstance(tag, dict) else getattr(tag, "key", None)
        if isinstance(key, str) and key != IS_PROMPT_TAG_KEY and key.strip().casefold() == wanted:
            return True
    return False


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
