"""
Audit logging module for MLflow OIDC Auth Plugin.

Provides structured audit logging for security-relevant operations:
permission changes, user management, authentication events, and admin actions.

Audit events are emitted via a dedicated Python logger (``mlflow_oidc_auth.audit``)
separate from the application logger, making it easy to route audit logs to a SIEM
or compliance pipeline via any standard log collector.

Configuration (environment variables / config providers):
    AUDIT_LOG_ENABLED  – Enable audit logging (default ``True``).
    AUDIT_LOG_LEVEL    – Log level for audit events: ``INFO`` or ``WARNING``
                         (default ``INFO``).

Each audit event is a single-line JSON object with the following fields:
    timestamp      – ISO-8601 UTC timestamp.
    event          – Action that occurred (e.g. ``permission.create``).
    actor          – Username of the user who performed the action.
    resource_type  – Type of resource affected (e.g. ``experiment_permission``).
    resource_id    – Identifier of the affected resource (may be ``None``).
    detail         – Free-form dict with additional context.
    status         – ``success`` or ``denied``.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional


# ---------------------------------------------------------------------------
# Audit logger — separate from the application logger so operators can
# route audit events independently (e.g. to a dedicated file / SIEM).
# ---------------------------------------------------------------------------
_AUDIT_LOGGER_NAME = "mlflow_oidc_auth.audit"
_audit_logger: Optional[logging.Logger] = None


def _get_audit_logger() -> logging.Logger:
    """Return (and lazily configure) the audit logger singleton."""
    global _audit_logger
    if _audit_logger is not None:
        return _audit_logger

    _audit_logger = logging.getLogger(_AUDIT_LOGGER_NAME)

    # Only add a handler if none exist yet (avoid duplicate handlers on reimport).
    if not _audit_logger.handlers:
        handler = logging.StreamHandler()
        # Emit the pre-formatted JSON message as-is — no extra decoration.
        handler.setFormatter(logging.Formatter("%(message)s"))
        _audit_logger.addHandler(handler)

    _audit_logger.propagate = False

    # Level is set dynamically per-call via _resolve_level(); the logger
    # itself should accept everything down to DEBUG so the handler decides.
    _audit_logger.setLevel(logging.DEBUG)

    return _audit_logger


def _is_enabled() -> bool:
    """Check whether audit logging is enabled via configuration."""
    try:
        from mlflow_oidc_auth.config import config

        return getattr(config, "AUDIT_LOG_ENABLED", True)
    except Exception:
        # If config is not yet initialised (e.g. during early startup or
        # unit tests), default to enabled so we never silently swallow events.
        return True


def _resolve_level() -> int:
    """Map the configured ``AUDIT_LOG_LEVEL`` string to a ``logging`` constant."""
    try:
        from mlflow_oidc_auth.config import config

        level_str = getattr(config, "AUDIT_LOG_LEVEL", "INFO")
    except Exception:
        level_str = "INFO"
    return getattr(logging, str(level_str).upper(), logging.INFO)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def emit_audit_event(
    event: str,
    actor: str,
    *,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    detail: Optional[Dict[str, Any]] = None,
    status: str = "success",
) -> None:
    """Emit a structured audit log event.

    Parameters:
        event:         Short action identifier, e.g. ``"permission.create"``.
        actor:         Username that performed the action.
        resource_type: Kind of resource affected (e.g. ``"experiment_permission"``).
        resource_id:   Identifier of the affected resource.
        detail:        Additional context as a dict (serialised to JSON).
        status:        Outcome — ``"success"`` (default) or ``"denied"``.
    """
    if not _is_enabled():
        return

    record: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "actor": actor,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "detail": detail or {},
        "status": status,
    }

    logger = _get_audit_logger()
    level = _resolve_level()
    logger.log(level, json.dumps(record, default=str))
