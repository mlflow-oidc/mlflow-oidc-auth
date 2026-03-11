"""Background scheduler for quota reconciliation and trash cleanup."""

from mlflow_oidc_auth.logger import get_logger

logger = get_logger()

try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    _apscheduler_available = True
except ImportError:
    _apscheduler_available = False
    logger.warning(
        "APScheduler is not installed. Background quota reconciliation and trash cleanup are disabled. "
        "Install apscheduler to enable: pip install apscheduler"
    )

_scheduler = None


def _run_reconcile_quotas():
    try:
        from mlflow_oidc_auth.utils.quota import reconcile_all_quotas

        reconcile_all_quotas()
    except Exception as e:
        logger.error(f"Quota reconciliation error: {e}")


def _run_cleanup_trash():
    try:
        from mlflow_oidc_auth.config import config
        from mlflow_oidc_auth.utils.quota import cleanup_trash

        cleanup_trash(config.QUOTA_TRASH_RETENTION_DAYS)
    except Exception as e:
        logger.error(f"Trash cleanup error: {e}")


def init_scheduler() -> None:
    """Start the background scheduler. Called once at app startup."""
    global _scheduler

    if not _apscheduler_available:
        return

    from mlflow_oidc_auth.config import config

    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(
        _run_reconcile_quotas,
        "interval",
        seconds=config.QUOTA_RECONCILE_INTERVAL_S,
        id="quota_reconcile",
        max_instances=1,
        coalesce=True,
    )
    # Run trash cleanup once per day (aligned to retention period for clarity)
    _scheduler.add_job(
        _run_cleanup_trash,
        "interval",
        seconds=86400,
        id="trash_cleanup",
        max_instances=1,
        coalesce=True,
    )
    _scheduler.start()
    logger.info(
        f"Background scheduler started: quota reconciliation every {config.QUOTA_RECONCILE_INTERVAL_S}s, "
        f"trash cleanup daily (retention: {config.QUOTA_TRASH_RETENTION_DAYS} days)"
    )


def shutdown_scheduler() -> None:
    """Stop the background scheduler. Called at app shutdown."""
    global _scheduler

    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Background scheduler stopped")
        _scheduler = None
