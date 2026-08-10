"""Applying migrations must not silence the process's logging (issue #342).

Alembic's ``env.py`` calls ``logging.config.fileConfig()``, whose ``disable_existing_loggers``
default is True. This plugin runs migrations from inside the server, on first access to the store
singleton — the first authenticated request — so every logger created at import time was being
disabled for the remaining life of the process.

The audit logger is the one that mattered: ``emit_audit_event`` kept building records and handing
them to a disabled logger, so the trail recorded nothing, with no error and no visible gap.

Each test drives a real ``init_db()``, because the defect is in what running migrations does to
the process, not in any function these tests could call directly.
"""

import io
import logging

import pytest

import mlflow_oidc_auth.audit as audit_module
from mlflow_oidc_auth.logger import get_logger


@pytest.fixture
def preserve_logging():
    """Snapshot and restore global logging state around a test.

    For tests that deliberately invoke ``fileConfig``: it swaps out the root logger's handlers,
    which in a pytest session means discarding the ``caplog`` handler and silently breaking
    capture for every test that runs afterwards.
    """
    root = logging.getLogger()
    saved_handlers = root.handlers[:]
    saved_level = root.level
    saved_disabled = {name: logger.disabled for name, logger in logging.root.manager.loggerDict.items() if isinstance(logger, logging.Logger)}
    try:
        yield
    finally:
        root.handlers[:] = saved_handlers
        root.setLevel(saved_level)
        for name, disabled in saved_disabled.items():
            logger = logging.root.manager.loggerDict.get(name)
            if isinstance(logger, logging.Logger):
                logger.disabled = disabled


@pytest.fixture
def migrated_store(tmp_path):
    """A store whose ``init_db`` has actually applied the migration chain."""
    from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore

    store = SqlAlchemyStore()
    store.init_db(f"sqlite:///{tmp_path / 'auth.db'}")
    yield store
    store.engine.dispose()


class TestApplicationLoggerSurvives:
    def test_plugin_logger_is_not_disabled(self, migrated_store):
        assert get_logger().disabled is False

    def test_plugin_logger_still_emits(self, tmp_path, caplog):
        """Not merely enabled — still actually producing records."""
        from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore

        logger = get_logger()
        SqlAlchemyStore().init_db(f"sqlite:///{tmp_path / 'auth.db'}")

        with caplog.at_level(logging.WARNING, logger=logger.name):
            logger.warning("emitted after the migration ran")

        assert any("emitted after the migration ran" in r.message for r in caplog.records)

    def test_uvicorn_loggers_are_not_disabled(self, migrated_store):
        """``alembic.ini`` names only root, sqlalchemy and alembic, so uvicorn's own loggers
        were collateral damage — the server's access and error logs went with them."""
        for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
            assert logging.getLogger(name).disabled is False, f"{name} was disabled by the migration"


class TestAuditTrailSurvives:
    """The damage that made #342 more than an observability annoyance."""

    @pytest.fixture
    def audit_output(self, monkeypatch):
        """Capture what the audit logger actually writes.

        It sets ``propagate = False`` and owns its handler, so ``caplog`` cannot see it; the
        handler's stream has to be replaced instead. Reading the real output is the point —
        asserting on a mock would not have caught this defect, because the call still happened.
        """
        monkeypatch.setattr(audit_module, "_audit_logger", None)
        logger = audit_module._get_audit_logger()
        stream = io.StringIO()
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
        handler = logging.StreamHandler(stream)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        yield stream
        logger.removeHandler(handler)
        monkeypatch.setattr(audit_module, "_audit_logger", None)

    def test_audit_events_are_written_after_migrations_run(self, audit_output, tmp_path):
        from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore

        audit_module.emit_audit_event("test.before", actor="probe", resource_type="user", resource_id="u1")

        SqlAlchemyStore().init_db(f"sqlite:///{tmp_path / 'auth.db'}")

        audit_module.emit_audit_event("test.after", actor="probe", resource_type="user", resource_id="u1")

        written = audit_output.getvalue()
        assert "test.before" in written, "precondition: auditing is on and capturing"
        assert "test.after" in written, "audit trail stopped recording once migrations ran"

    def test_audit_logger_is_not_disabled(self, audit_output, migrated_store):
        assert audit_module._get_audit_logger().disabled is False


class TestEnvPyGuards:
    """The two conditions in env.py, checked directly so a later edit cannot quietly drop one."""

    def test_the_embedded_helper_marks_itself_as_not_configuring_logging(self, tmp_path):
        """The signal is explicit, not inferred.

        The first attempt keyed off ``attributes["connection"]``, which ``migrate_if_needed`` —
        the function that actually runs at startup — never sets, so the guard missed the real
        path entirely.
        """
        from mlflow_oidc_auth.db.utils import _get_alembic_config

        cfg = _get_alembic_config(f"sqlite:///{tmp_path / 'auth.db'}")

        assert cfg.attributes.get("configure_logging") is False
        assert cfg.config_file_name is not None, "precondition: the ini path is set, so the flag is what skips it"

    def test_init_db_leaves_the_root_handlers_alone(self, tmp_path):
        """The property that actually broke: ``fileConfig`` swaps out root's handlers.

        That is what discarded pytest's ``caplog`` handler mid-session, and in a deployment it
        is what would replace an operator's own root logging configuration.
        """
        from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore

        root = logging.getLogger()
        before = root.handlers[:]

        SqlAlchemyStore().init_db(f"sqlite:///{tmp_path / 'auth.db'}")

        assert root.handlers == before

    def test_cli_style_config_does_not_disable_existing_loggers(self, tmp_path, preserve_logging):
        """Even where Alembic owns the process, existing loggers must survive.

        ``preserve_logging`` is not optional here: ``fileConfig`` replaces the *root* handlers,
        which would take pytest's own ``caplog`` handler with it and break unrelated tests later
        in the session — the same global-state damage this issue is about.
        """
        from logging.config import fileConfig

        from mlflow_oidc_auth.db.utils import _get_alembic_config

        marker = logging.getLogger("test.cli.marker")
        marker.disabled = False
        cfg = _get_alembic_config(f"sqlite:///{tmp_path / 'auth.db'}")

        fileConfig(cfg.config_file_name, disable_existing_loggers=False)

        assert marker.disabled is False
