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
from typing import Any, Optional

from mlflow_oidc_auth.utils.permissions import can_use_gateway_endpoint, can_use_gateway_secret
from mlflow_oidc_auth.validators._model_uri import gateway_endpoint_for_name, is_gateway_provider, split_model_uri

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


def can_use_secret_id(secret_id: str, username: str) -> bool:
    """USE on the gateway secret ``secret_id`` names; an id that resolves to no secret denies."""
    # validators.gateway imports validators.experiment (through _referenced), which imports this module.
    from mlflow_oidc_auth.validators.gateway import _resolve_secret_name_from_id

    secret_name = _resolve_secret_name_from_id(str(secret_id))
    return bool(secret_name) and can_use_gateway_secret(secret_name, username)


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


def _stored_model_permitted(model: object, username: str) -> bool:
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
    if provider and model_name and not _model_uri_permitted(f"{provider.lower()}:/{model_name}", username):
        return False
    return True


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

    The check is made when the tag is written. The scheduler runs a stored schedule with no
    identity, so revoking the writer's USE afterwards does not stop it; deleting the tag does.

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
    for raw in raw_values:
        try:
            envelope = json.loads(str(raw))
        except (ValueError, RecursionError):
            return False
        if not isinstance(envelope, dict) or not _stored_model_permitted(envelope.get("model"), username):
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
        if not _model_uri_permitted(model.to_model_uri(), username):
            return False
    return True


def detection_schedule_values_in_tags(tags: object) -> list:
    """The values a CreateExperiment ``tags`` list would store under the detection schedule tag."""
    if not isinstance(tags, list):
        return []
    return [tag.get("value") for tag in tags if isinstance(tag, dict) and tag.get("key") == DETECTION_SCHEDULE_TAG]
