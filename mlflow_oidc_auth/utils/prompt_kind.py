"""Which permissions decide access to a registered model: its own, or a prompt's (#479).

MLflow stores a prompt as a registered model tagged ``mlflow.prompt.is_prompt = "true"``, and its
versions as model versions. Every prompt call therefore reaches the plugin as a registered-model or
model-version request. Prompt patterns are kept apart from model patterns (exact-name grants are
shared), so the resolver has to follow the target's kind, which only MLflow knows.
"""

from contextvars import ContextVar
from typing import Any, Optional

from mlflow.exceptions import MlflowException
from mlflow.prompt.constants import IS_PROMPT_TAG_KEY
from mlflow.protos.databricks_pb2 import RESOURCE_DOES_NOT_EXIST, ErrorCode

from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.models import PermissionResult

logger = get_logger()

_MEMO = "_mlflow_oidc_prompt_kinds"

# Outside a Flask request (FastAPI routes and dependencies) the memo lives here, tied to the
# request's AuthContext object: each request gets a new one, so an entry never outlives its request
# and nothing is shared between concurrent requests (a ContextVar is per asyncio task).
_fastapi_memo: ContextVar[Optional[tuple]] = ContextVar("_mlflow_oidc_prompt_kind_memo", default=None)


def is_kind_key(key: Any) -> bool:
    """Whether a tag key names ``mlflow.prompt.is_prompt``, ignoring case and surrounding whitespace.

    MySQL and SQL Server compare tag keys that way, so every spelling reaches the stored kind tag.

    Parameters:
        key: A tag key from a request.

    Returns:
        True when the key is any spelling of the kind tag.
    """
    return isinstance(key, str) and key.strip().casefold() == IS_PROMPT_TAG_KEY.casefold()


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
    """The current request's name-to-kind memo, or None outside a request.

    A Flask request keeps it on ``flask.g``. A FastAPI request keeps it on a ContextVar bound to the
    request's AuthContext; with no AuthContext there is no request, and nothing is remembered.
    """
    from flask import g, has_request_context

    if has_request_context():
        memo = getattr(g, _MEMO, None)
        if memo is None:
            memo = {}
            setattr(g, _MEMO, memo)
        return memo
    from mlflow_oidc_auth.bridge.user import _auth_context_var

    owner = _auth_context_var.get()
    if owner is None:
        return None
    held = _fastapi_memo.get()
    if held is None or held[0] is not owner:
        held = (owner, {})
        _fastapi_memo.set(held)
    return held[1]


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

    for tag in (request_body_dict() or {}).get("tags") or ():
        key = tag.get("key") if isinstance(tag, dict) else getattr(tag, "key", None)
        if key != IS_PROMPT_TAG_KEY and is_kind_key(key):
            return True
    return False


def request_creates_prompt() -> bool:
    """Whether the current create request makes a prompt, by its own tags.

    At creation the model may not exist yet, so its tags cannot be looked up. The value rule is the
    one MLflow applies to the stored model (``RegisteredModel._is_prompt``: the tag is ``"true"``,
    any case), so the decision here matches how the new model is judged afterwards. MLflow's own
    ``handlers._is_prompt_request`` only checks that the key is present, for webhook routing.

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
