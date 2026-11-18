"""MLflow 3.18's recurring issue-detection schedule, as an experiment tag the plugin authorizes.

MLflow keeps the schedule in the ``mlflow.issueDetection.schedule`` experiment tag, written through
``set-experiment-tag`` or on ``create``, and its scheduler runs every occurrence on the model the
tag names. Writing the tag is therefore authorized like starting detection on that model.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
from collections.abc import Callable, Iterable
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator, Optional

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.utils.permissions import can_use_gateway_endpoint, can_use_gateway_secret
from mlflow_oidc_auth.validators._model_uri import gateway_endpoint_for_name, is_gateway_provider, split_model_uri

logger = get_logger()

_SCHEDULE_MODULE = "mlflow.genai.discovery.schedule"


def _mlflow_schedule_parser() -> Optional[Callable[..., Any]]:
    """MLflow's own schedule parser, or ``None`` on an MLflow that has no scheduler.

    Only a missing module means "no scheduler". A module that exists but cannot be imported, or no
    longer has the parser, raises, and the caller denies: MLflow internals moving must never turn
    this check off.
    """
    try:
        present = importlib.util.find_spec(_SCHEDULE_MODULE) is not None
    except ModuleNotFoundError:
        present = False
    if not present:
        return None
    return importlib.import_module(_SCHEDULE_MODULE).parse_detection_schedule


#: Set by the schedule guard: an error that is not a definite answer (not "no such secret", not
#: "unknown provider") raises instead of denying, so a transient fault is retried rather than
#: pausing a healthy schedule. Requests keep denying on every error.
_RAISE_UNCERTAIN: ContextVar[bool] = ContextVar("detection_schedule_raise_uncertain", default=False)

_DEFINITE_ERRORS = ("RESOURCE_DOES_NOT_EXIST", "INVALID_PARAMETER_VALUE")


@contextmanager
def raise_uncertain_errors() -> Iterator[None]:
    """Within this block, a check that cannot decide raises rather than denying."""
    token = _RAISE_UNCERTAIN.set(True)
    try:
        yield
    finally:
        _RAISE_UNCERTAIN.reset(token)


def _is_definite(error: Exception) -> bool:
    from mlflow.exceptions import MlflowException

    return isinstance(error, MlflowException) and error.error_code in _DEFINITE_ERRORS


def can_use_secret_id(secret_id: str, username: str) -> bool:
    """USE on the gateway secret ``secret_id`` names; an id that resolves to no secret denies."""
    if _RAISE_UNCERTAIN.get():
        from mlflow.server.handlers import _get_tracking_store

        try:
            secret_name = _get_tracking_store().get_secret_info(secret_id=str(secret_id)).secret_name
        except Exception as e:
            if _is_definite(e):
                return False
            raise
        return bool(secret_name) and can_use_gateway_secret(secret_name, username)
    # validators.gateway imports validators.experiment (through _referenced), which imports this module.
    from mlflow_oidc_auth.validators.gateway import _resolve_secret_name_from_id

    secret_name = _resolve_secret_name_from_id(str(secret_id))
    return bool(secret_name) and can_use_gateway_secret(secret_name, username)


def _required_credential_variables(env_var_config: object) -> set:
    """The environment variables a secret must supply itself for MLflow's provider table entry.

    The API key of a key-based provider, or every variable of one authenticated by a set of them
    (Bedrock's optional session token aside).
    """
    if isinstance(env_var_config, dict):
        if "api_key" in env_var_config:
            return {env_var_config["api_key"]}
        return {name for key, name in env_var_config.items() if key != "aws_session_token"}
    return {env_var_config} if isinstance(env_var_config, str) else set()


def secret_supplies_provider_credentials(provider: object, secret_id: object, memo: Optional[dict] = None) -> bool:
    """Whether the secret ``secret_id`` itself carries ``provider``'s credentials, as MLflow reads it.

    MLflow turns a named secret into environment variables for the job
    (``mlflow.genai.discovery.job._fetch_provider_credentials``) on top of the server's own
    environment, so a named secret must supply every credential variable itself. This reads the
    secret with MLflow's own function; an unknown provider, a secret that cannot be read, or an
    MLflow that no longer has the function denies. Answers are cached for the request (or in
    ``memo``), so a secret named twice is decrypted once.
    """
    if not isinstance(provider, str) or not provider or not isinstance(secret_id, str) or not secret_id:
        return False
    if memo is None:
        memo = _request_memo()
    key = (provider.lower(), secret_id)
    if memo is not None and key in memo:
        return memo[key]
    supplied = _secret_supplies_provider_credentials(provider, secret_id)
    if memo is not None:
        memo[key] = supplied
    return supplied


def _request_memo() -> Optional[dict]:
    """A per-request cache of credential answers, or None outside a request."""
    from flask import g, has_request_context

    if not has_request_context():
        return None
    if not hasattr(g, "_oidc_secret_credentials"):
        g._oidc_secret_credentials = {}
    return g._oidc_secret_credentials


def _secret_supplies_provider_credentials(provider: str, secret_id: str) -> bool:
    try:
        # mlflow.server.jobs.utils first: its post-import hook builds MLflow's job-name map by
        # importing every job module, so importing the job module first registers it half-loaded
        # and leaves issue detection out of the map for the life of the process.
        import mlflow.server.jobs.utils  # noqa: F401
        from mlflow.genai.discovery.job import _fetch_provider_credentials
        from mlflow.server.handlers import _get_tracking_store
        from mlflow.utils.providers import _CORE_PROVIDER_ENV_VARS

        # MLflow lower-cases the provider and nothing else.
        name = provider.lower()
        required = _required_credential_variables(_CORE_PROVIDER_ENV_VARS.get(name))
        if not required:
            return False
        supplied = _fetch_provider_credentials(_get_tracking_store(), name, secret_id)
    except Exception as e:
        if _RAISE_UNCERTAIN.get() and not _is_definite(e):
            raise
        # Never the secret's values: only that it could not be read, and why in type.
        logger.warning("Could not read gateway secret %s for provider %s (%s); denying", secret_id, provider, type(e).__name__)
        return False
    return isinstance(supplied, dict) and all(supplied.get(variable) for variable in required)


def can_use_endpoint_name(name: str, username: str) -> bool:
    """USE on the endpoint MLflow calls for ``name``, and on ``name`` as given.

    MLflow calls the endpoint parsed from ``gateway:/<name>``, which strips leading slashes.
    """
    called = gateway_endpoint_for_name(str(name))
    return called is not None and can_use_gateway_endpoint(called, username) and can_use_gateway_endpoint(str(name), username)


#: The experiment tag MLflow 3.18's issue-detection scheduler reads its schedule, model included, from.
DETECTION_SCHEDULE_TAG = "mlflow.issueDetection.schedule"


def _model_uri_permitted(model_uri: str, username: str) -> bool:
    """A gateway model URI needs USE on the endpoint MLflow calls; another provider's is unchecked,
    as on ``issues/invoke``. A URI MLflow cannot parse denies."""
    parsed = split_model_uri(model_uri)
    if parsed is None:
        return False
    provider, name = parsed
    return not is_gateway_provider(provider) or can_use_gateway_endpoint(name, username)


def _usable_text(value: object) -> str:
    """``value`` stripped when it is a non-empty string, else ``""``."""
    return value.strip() if isinstance(value, str) else ""


def _stored_model_permitted(model: object, username: str, memo: Optional[dict] = None) -> bool:
    """Every model reference in a stored schedule envelope, whichever of them a parser would use.

    Read independently of MLflow's parser, and more strictly: a field of the wrong type denies, and
    an endpoint, a secret and a provider model in one envelope are all checked. So a value this
    MLflow ignores (an MLflow without the scheduler, an envelope version it does not know) cannot
    name a model nobody checked that a later MLflow would run.
    """
    if model is None:
        return True
    if not isinstance(model, dict):
        return False
    fields = {key: model.get(key) for key in ("endpointName", "secretId", "provider", "model")}
    if any(value is not None and not isinstance(value, str) for value in fields.values()):
        return False
    endpoint_name = _usable_text(fields["endpointName"])
    if endpoint_name and not can_use_endpoint_name(endpoint_name, username):
        return False
    # The scheduler looks the secret up by the id as stored, not stripped.
    if _usable_text(fields["secretId"]) and not can_use_secret_id(fields["secretId"], username):
        return False
    provider, model_name = _usable_text(fields["provider"]), _usable_text(fields["model"])
    # With an endpoint named, the scheduler runs on that endpoint and the secret's values go unused.
    if _usable_text(fields["secretId"]) and provider and not endpoint_name and not is_gateway_provider(provider):
        if not secret_supplies_provider_credentials(fields["provider"], fields["secretId"], memo):
            return False
    if provider and model_name and not _model_uri_permitted(f"{provider.lower()}:/{model_name}", username):
        return False
    return True


def _raw_model_uses_server_credentials(model: object) -> bool:
    """Whether a stored model reference, read as stored, leaves MLflow on its own credentials."""
    if not isinstance(model, dict):
        # No model (or one MLflow cannot read): the job runs MLflow's default model.
        return True
    if _usable_text(model.get("endpointName")):
        return False
    if is_gateway_provider(_usable_text(model.get("provider")).lower()):
        return False
    return not _usable_text(model.get("secretId"))


def schedule_uses_server_credentials(raw: object) -> bool:
    """Whether MLflow would run the schedule ``raw`` on the server's own provider credentials.

    That is a schedule naming no model (MLflow then uses its default model), or a provider model
    with no stored secret: MLflow's scheduler passes the job no credential of its own, so the
    provider call uses whatever key the server's environment holds. A gateway endpoint, or a
    provider model with a secret, does not. Read both as stored and as MLflow's parser reads the
    value, and true when either reading leaves the server's credentials in use; a value that cannot
    be read at all counts as using them.
    """
    try:
        envelope = json.loads(str(raw))
    except (ValueError, RecursionError):
        return True
    if not isinstance(envelope, dict) or _raw_model_uses_server_credentials(envelope.get("model")):
        return True
    try:
        parse_detection_schedule = _mlflow_schedule_parser()
        schedule = parse_detection_schedule(str(raw)) if parse_detection_schedule is not None else None
    except Exception:
        return True
    if schedule is None:
        return False
    model = schedule.model
    if model is None:
        return True
    if model.endpoint_name or is_gateway_provider(model.provider.lower()):
        return False
    return not model.secret_id


def detection_schedules_permitted(raw_values: Iterable[object], username: str) -> bool:
    """USE on every gateway endpoint or secret the detection schedules in ``raw_values`` name.

    MLflow 3.18 keeps an experiment's recurring issue detection in the
    ``mlflow.issueDetection.schedule`` experiment tag, and its scheduler runs each occurrence on
    the model that tag names: a gateway endpoint (named directly, or as the ``gateway`` provider),
    or a provider model with a stored secret the scheduler decrypts. Writing the tag is therefore
    the same as starting detection on that endpoint or secret, and needs the USE that
    ``issues/invoke`` needs for it.

    Each value must be a JSON object, as every schedule MLflow writes is. Its model references are
    checked twice: as stored (see :func:`_stored_model_permitted`), and, where this MLflow has the
    scheduler, as MLflow's own parser reads them, so what the scheduler will run is authorized
    whatever the parser makes of the envelope.

    With ``ISSUE_DETECTION_SERVER_CREDENTIALS_ADMIN_ONLY`` on, a schedule that would run on the
    server's own provider credentials (see ``schedule_uses_server_credentials``) is refused
    too. Validators run for non-administrators only.

    The check is made when the tag is written. The scheduler runs a stored schedule with no
    identity, so ``mlflow_oidc_auth.issue_detection_guard`` re-checks stored schedules against
    their recorded writer and pauses one the writer could no longer write.

    Parameters:
        raw_values: The values the request would store under the schedule tag.
        username: The authenticated user.

    Returns:
        True when every value is a schedule envelope whose models the user may all use.
    """
    try:
        parse_detection_schedule = _mlflow_schedule_parser()
    except Exception:
        return False
    memo = _request_memo()
    if memo is None:
        memo = {}
    for raw in raw_values:
        try:
            envelope = json.loads(str(raw))
        except (ValueError, RecursionError):
            return False
        if not isinstance(envelope, dict) or not _stored_model_permitted(envelope.get("model"), username, memo):
            return False
        if config.ISSUE_DETECTION_SERVER_CREDENTIALS_ADMIN_ONLY and schedule_uses_server_credentials(raw):
            return False
        if parse_detection_schedule is None:
            continue
        try:
            schedule = parse_detection_schedule(str(raw))
        except Exception:
            return False
        model = schedule.model if schedule is not None else None
        if model is None:
            continue
        if model.secret_id and not can_use_secret_id(model.secret_id, username):
            return False
        if (
            model.secret_id
            and not model.endpoint_name
            and not is_gateway_provider(str(model.provider or ""))
            and not secret_supplies_provider_credentials(model.provider, model.secret_id, memo)
        ):
            return False
        if not _model_uri_permitted(model.to_model_uri(), username):
            return False
    return True


def detection_schedule_values_in_tags(tags: object) -> list:
    """The values a CreateExperiment ``tags`` list would store under the detection schedule tag."""
    if not isinstance(tags, list):
        return []
    return [tag.get("value") for tag in tags if isinstance(tag, dict) and tag.get("key") == DETECTION_SCHEDULE_TAG]
