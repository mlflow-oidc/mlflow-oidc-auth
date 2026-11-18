"""Tell the issue detection schedule guard that grants, memberships or users changed.

One helper for every caller (the permission cache, the workspace cache, user updates). It imports
the guard lazily and never raises: a signal that cannot be delivered must never get in the way of
the invalidation or update it accompanies, and the guard's periodic pass covers it anyway.
"""

from mlflow_oidc_auth.logger import get_logger

logger = get_logger()


def notify_schedule_guard() -> None:
    """Ask the schedule guard for a pass soon. Never raises."""
    try:
        from mlflow_oidc_auth.issue_detection_guard import permissions_changed

        permissions_changed()
    except Exception:
        logger.debug("Could not notify the issue detection schedule guard", exc_info=True)
