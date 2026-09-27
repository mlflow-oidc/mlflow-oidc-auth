"""Parsing of ``<provider>:/<model-name>`` model URIs, exactly as MLflow parses them.

An authorization decision on a gateway endpoint named by a model URI must be made on the
endpoint MLflow will call. MLflow splits the URI on the first ``:/`` and strips leading
slashes from the name, so ``gateway:/x``, ``gateway://x`` and ``gateway:///x`` all call
endpoint ``x``.
"""

from __future__ import annotations

_GATEWAY_PROVIDER = "gateway"


def _fallback_parse(model_uri: str) -> tuple[str, str]:
    # Same logic as mlflow.metrics.genai.model_utils._parse_model_uri (MLflow 3.16.1).
    parts = model_uri.split(":/", 1)
    if len(parts) != 2 or not parts[0] or not parts[1].lstrip("/"):
        raise ValueError("malformed model uri")
    return parts[0], parts[1].lstrip("/")


def split_model_uri(model_uri: str) -> tuple[str, str] | None:
    """Split a model URI into ``(provider, name)`` with MLflow's own parser.

    Parameters:
        model_uri: A ``<provider>:/<model-name>`` URI.

    Returns:
        ``(provider, name)``, or None if MLflow would reject the URI as malformed.
    """
    try:
        from mlflow.metrics.genai.model_utils import _parse_model_uri
    except ImportError:  # pragma: no cover - private MLflow helper moved
        _parse_model_uri = _fallback_parse
    try:
        return _parse_model_uri(model_uri)
    except Exception:
        return None


def is_gateway_provider(provider: str) -> bool:
    """True for the gateway provider. Trimmed and case-insensitive, so a spelling variant is
    checked as a gateway endpoint rather than left unchecked."""
    return provider.strip().lower() == _GATEWAY_PROVIDER


def gateway_endpoint_for_name(endpoint_name: str) -> str | None:
    """The endpoint MLflow calls for ``gateway:/<endpoint_name>``, which is how the
    ``issues/invoke`` handler builds its model URI; None if that URI is malformed."""
    parsed = split_model_uri(f"{_GATEWAY_PROVIDER}:/{endpoint_name}")
    return parsed[1] if parsed else None
