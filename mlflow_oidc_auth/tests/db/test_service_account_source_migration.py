"""Service account sign-in source migration: every existing service account becomes internal.

Runs on SQLite, and on PostgreSQL when ``MLFLOW_OIDC_TEST_POSTGRES_URI`` is set (skipped otherwise).
"""

from sqlalchemy import inspect, text

from mlflow_oidc_auth.tests.db.test_phase0_migration import (  # noqa: F401  (fixtures)
    _downgrade,
    _upgrade,
    db_uri,
    engine,
)

PREVIOUS_REVISION = "d0e1f2a3b4c5"
REVISION = "e1f2a3b4c5d6"


def _seed(engine) -> None:
    with engine.begin() as conn:
        for username, is_service_account in (
            ("alice@example.com", False),
            ("ci-bot", True),
            ("trainer.ml@serviceaccount.cluster.local", True),
        ):
            conn.execute(
                text("INSERT INTO users (username, display_name, is_admin, is_service_account, active, managed_by) " "VALUES (:u, :u, :f, :sa, :t, 'manual')"),
                {"u": username, "f": False, "sa": is_service_account, "t": True},
            )


def _sources(engine):
    with engine.connect() as conn:
        return dict(conn.execute(text("SELECT username, service_account_source FROM users")).fetchall())


def test_service_accounts_become_internal_and_kubernetes_ones_their_providers(engine):
    _upgrade(engine, PREVIOUS_REVISION)
    _seed(engine)

    _upgrade(engine, REVISION)

    assert _sources(engine) == {
        "alice@example.com": None,
        "ci-bot": "internal",
        "trainer.ml@serviceaccount.cluster.local": "kubernetes",
    }


def test_round_trip(engine):
    _upgrade(engine, PREVIOUS_REVISION)
    _seed(engine)

    _upgrade(engine, REVISION)
    _downgrade(engine, PREVIOUS_REVISION)

    assert "service_account_source" not in {c["name"] for c in inspect(engine).get_columns("users")}
    _upgrade(engine, REVISION)
    assert _sources(engine)["ci-bot"] == "internal"
