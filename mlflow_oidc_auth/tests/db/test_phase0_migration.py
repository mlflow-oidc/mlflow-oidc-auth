"""Phase 0 schema migration: heads, round-trip and backfill (issue #333).

The migration itself is mechanical; what these tests defend are the two backfill choices that
later issues depend on, and the head invariant that motivated putting all of Phase 0 in one
revision.

**Postgres.** Every test here runs against SQLite, and against PostgreSQL too when
``MLFLOW_OIDC_TEST_POSTGRES_URI`` is set (skipped otherwise, so the default suite stays
dependency-free). CI should set it — a migration verified on one backend is verified on one
backend. Run locally with, for example::

    MLFLOW_OIDC_TEST_POSTGRES_URI=postgresql+psycopg2://user@127.0.0.1:5432/test \\
        pytest mlflow_oidc_auth/tests/db/test_phase0_migration.py
"""

import os

import pytest
from alembic.command import downgrade, upgrade
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

from mlflow_oidc_auth.db.utils import _get_alembic_config

PREVIOUS_REVISION = "8a9b0c1de234"
PHASE0_REVISION = "9c0d1e2f3456"

POSTGRES_URI = os.environ.get("MLFLOW_OIDC_TEST_POSTGRES_URI")


def _sqlite_uri(tmp_path) -> str:
    return f"sqlite:///{tmp_path / 'auth.db'}"


@pytest.fixture(params=["sqlite", "postgres"])
def db_uri(request, tmp_path):
    """A database URI per backend. Postgres cases skip unless a server is configured."""
    if request.param == "sqlite":
        return _sqlite_uri(tmp_path)
    if not POSTGRES_URI:
        pytest.skip("MLFLOW_OIDC_TEST_POSTGRES_URI is not set")
    return POSTGRES_URI


@pytest.fixture
def engine(db_uri):
    eng = create_engine(db_uri)
    if eng.dialect.name == "postgresql":
        # Start from a clean slate: the migration chain owns the public schema for this run.
        with eng.begin() as conn:
            conn.execute(text("DROP SCHEMA public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
    yield eng
    eng.dispose()


def _alembic_config(engine):
    """An Alembic config that does not reconfigure this process's logging.

    ``env.py`` calls ``logging.config.fileConfig()``, which defaults to
    ``disable_existing_loggers=True`` and therefore silences every logger created before it
    runs. That is survivable once at application startup, but these tests invoke Alembic dozens
    of times mid-session, and the collateral damage is unrelated tests losing their ``caplog``
    records. Clearing the filename makes ``env.py`` skip the call.
    """
    cfg = _get_alembic_config(engine.url.render_as_string(hide_password=False))
    cfg.config_file_name = None
    return cfg


def _upgrade(engine, revision: str) -> None:
    cfg = _alembic_config(engine)
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        upgrade(cfg, revision)


def _downgrade(engine, revision: str) -> None:
    cfg = _alembic_config(engine)
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        downgrade(cfg, revision)


def _seed_legacy_data(engine) -> None:
    """Insert users, groups and memberships as they exist at the previous revision.

    Raw SQL on purpose: the ORM models already carry the Phase 0 columns, so using them here
    would not reproduce a pre-migration database.
    """
    with engine.begin() as conn:
        for i, name in enumerate(["alice@example.com", "bob@example.com", "svc@example.com"], start=1):
            conn.execute(
                text("INSERT INTO users (username, display_name, password_hash, is_admin, is_service_account) " "VALUES (:u, :d, :h, :a, :s)"),
                {"u": name, "d": name, "h": "not-a-real-hash", "a": i == 1, "s": i == 3},
            )
        conn.execute(text("INSERT INTO groups (group_name) VALUES ('legacy-team')"))
        conn.execute(
            text("INSERT INTO user_groups (user_id, group_id) " "SELECT users.id, groups.id FROM users, groups WHERE groups.group_name = 'legacy-team'")
        )


class TestRevisionChain:
    def test_exactly_one_head(self, tmp_path):
        """The invariant that put all of Phase 0 in one revision.

        Three parallel revisions off the same parent would give three heads and make
        ``alembic upgrade head`` fail outright for every deployment.
        """
        cfg = _get_alembic_config(_sqlite_uri(tmp_path))
        heads = ScriptDirectory.from_config(cfg).get_heads()

        assert heads == [PHASE0_REVISION], f"expected a single head, got {heads}"

    def test_phase0_follows_the_previous_head(self, tmp_path):
        cfg = _get_alembic_config(_sqlite_uri(tmp_path))
        script = ScriptDirectory.from_config(cfg).get_revision(PHASE0_REVISION)

        assert script.down_revision == PREVIOUS_REVISION


class TestUpgradeFromEmpty:
    def test_upgrade_head_creates_the_phase0_schema(self, engine):
        _upgrade(engine, "head")

        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        assert {"user_identities", "auth_sessions", "auth_state"} <= tables
        assert {"active", "managed_by", "external_id", "created_at", "updated_at"} <= {c["name"] for c in inspector.get_columns("users")}
        assert "managed_by" in {c["name"] for c in inspector.get_columns("user_groups")}
        assert {"external_id", "created_at", "updated_at"} <= {c["name"] for c in inspector.get_columns("groups")}

    def test_active_is_not_nullable(self, engine):
        """A nullable or false-defaulting ``active`` would deny every user once #311 enforces it."""
        _upgrade(engine, "head")

        active = next(c for c in inspect(engine).get_columns("users") if c["name"] == "active")

        assert active["nullable"] is False


class TestUpgradeFromPreviousRevision:
    """The path a real deployment takes: an existing database with data in it."""

    def test_upgrade_succeeds_over_existing_data(self, engine):
        _upgrade(engine, PREVIOUS_REVISION)
        _seed_legacy_data(engine)

        _upgrade(engine, "head")

        with engine.connect() as conn:
            assert conn.execute(text("SELECT count(*) FROM users")).scalar() == 3

    def test_existing_users_are_active(self, engine):
        _upgrade(engine, PREVIOUS_REVISION)
        _seed_legacy_data(engine)

        _upgrade(engine, "head")

        with engine.connect() as conn:
            inactive = conn.execute(text("SELECT count(*) FROM users WHERE active <> :t"), {"t": True}).scalar()
        assert inactive == 0, "an existing user would be denied at next login"

    def test_existing_users_are_labelled_manual(self, engine):
        """Not ``oidc:default``.

        Mislabelling pre-existing rows as provider-managed would let the #319 write guard refuse
        admin edits to memberships that were in fact manual — up to locking every admin out of
        their own permission data, which needs out-of-band access to recover from.
        """
        _upgrade(engine, PREVIOUS_REVISION)
        _seed_legacy_data(engine)

        _upgrade(engine, "head")

        with engine.connect() as conn:
            labels = {r[0] for r in conn.execute(text("SELECT DISTINCT managed_by FROM users"))}
        assert labels == {"manual"}

    def test_existing_memberships_are_labelled_manual(self, engine):
        """Same reasoning as above, for the rows #319 actually guards."""
        _upgrade(engine, PREVIOUS_REVISION)
        _seed_legacy_data(engine)

        _upgrade(engine, "head")

        with engine.connect() as conn:
            labels = {r[0] for r in conn.execute(text("SELECT DISTINCT managed_by FROM user_groups"))}
        assert labels == {"manual"}

    def test_every_existing_user_gets_exactly_one_identity(self, engine):
        """No user may be stranded, and none may be duplicated."""
        _upgrade(engine, PREVIOUS_REVISION)
        _seed_legacy_data(engine)

        _upgrade(engine, "head")

        with engine.connect() as conn:
            rows = conn.execute(text("SELECT provider_id, subject, user_id FROM user_identities ORDER BY user_id")).fetchall()
            usernames = [r[0] for r in conn.execute(text("SELECT username FROM users ORDER BY id"))]

        assert len(rows) == 3
        assert {r[0] for r in rows} == {"default"}
        assert [r[1] for r in rows] == usernames, "subject must be the username current lookups key on"

    def test_backfill_is_empty_on_a_database_with_no_users(self, engine):
        """The INSERT ... SELECT must not invent a row when there is nothing to migrate."""
        _upgrade(engine, PREVIOUS_REVISION)

        _upgrade(engine, "head")

        with engine.connect() as conn:
            assert conn.execute(text("SELECT count(*) FROM user_identities")).scalar() == 0


class TestRoundTrip:
    def test_downgrade_then_upgrade(self, engine):
        """Migrations must be reversible on both backends."""
        _upgrade(engine, "head")

        _downgrade(engine, "-1")

        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        assert not ({"user_identities", "auth_sessions", "auth_state"} & tables), "downgrade left tables behind"
        assert "active" not in {c["name"] for c in inspector.get_columns("users")}
        assert "managed_by" not in {c["name"] for c in inspector.get_columns("user_groups")}

        _upgrade(engine, "head")

        inspector = inspect(engine)
        assert {"user_identities", "auth_sessions", "auth_state"} <= set(inspector.get_table_names())
        assert "active" in {c["name"] for c in inspector.get_columns("users")}

    def test_round_trip_preserves_pre_existing_data(self, engine):
        """Reversibility is worth nothing if it takes the users with it."""
        _upgrade(engine, PREVIOUS_REVISION)
        _seed_legacy_data(engine)
        _upgrade(engine, "head")

        _downgrade(engine, "-1")
        _upgrade(engine, "head")

        with engine.connect() as conn:
            assert conn.execute(text("SELECT count(*) FROM users")).scalar() == 3
            assert conn.execute(text("SELECT count(*) FROM user_groups")).scalar() == 3
            # The second upgrade re-runs the backfill against the same three users.
            assert conn.execute(text("SELECT count(*) FROM user_identities")).scalar() == 3


class TestExternalIdUniqueness:
    """``external_id`` is unique when present, which must still allow many absent ones."""

    def test_multiple_null_external_ids_are_allowed(self, engine):
        _upgrade(engine, "head")

        with engine.begin() as conn:
            for name in ["u1@example.com", "u2@example.com"]:
                conn.execute(
                    text("INSERT INTO users (username, display_name, password_hash, active, managed_by) VALUES (:u, :u, :h, :a, 'manual')"),
                    {"u": name, "h": "not-a-real-hash", "a": True},
                )

        with engine.connect() as conn:
            assert conn.execute(text("SELECT count(*) FROM users WHERE external_id IS NULL")).scalar() == 2

    def test_duplicate_external_ids_are_rejected(self, engine):
        """The negative case: uniqueness must actually be enforced, not merely declared."""
        from sqlalchemy.exc import IntegrityError

        _upgrade(engine, "head")

        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO users (username, display_name, password_hash, active, managed_by, external_id) "
                    "VALUES ('e1@example.com', 'e1', :h, :a, 'manual', 'shared-id')"
                ),
                {"h": "not-a-real-hash", "a": True},
            )

        with pytest.raises(IntegrityError):
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "INSERT INTO users (username, display_name, password_hash, active, managed_by, external_id) "
                        "VALUES ('e2@example.com', 'e2', :h, :a, 'manual', 'shared-id')"
                    ),
                    {"h": "not-a-real-hash", "a": True},
                )


class TestIdentityUniqueness:
    def test_the_same_subject_cannot_be_claimed_twice_for_one_provider(self, engine):
        """Two accounts sharing a ``(provider, subject)`` would be an account-takeover primitive."""
        from sqlalchemy.exc import IntegrityError

        _upgrade(engine, PREVIOUS_REVISION)
        _seed_legacy_data(engine)
        _upgrade(engine, "head")

        with pytest.raises(IntegrityError):
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "INSERT INTO user_identities (provider_id, subject, user_id) "
                        "SELECT 'default', 'alice@example.com', id FROM users WHERE username = 'bob@example.com'"
                    )
                )

    def test_the_same_subject_may_exist_under_a_different_provider(self, engine):
        _upgrade(engine, PREVIOUS_REVISION)
        _seed_legacy_data(engine)
        _upgrade(engine, "head")

        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO user_identities (provider_id, subject, user_id) "
                    "SELECT 'okta', 'alice@example.com', id FROM users WHERE username = 'alice@example.com'"
                )
            )

        with engine.connect() as conn:
            assert conn.execute(text("SELECT count(*) FROM user_identities WHERE subject = 'alice@example.com'")).scalar() == 2
