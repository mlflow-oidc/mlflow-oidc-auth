"""Phase 0 schema migration: heads, round-trip and backfill (issue #333).

The migration itself is mechanical; what these tests defend are the two backfill choices that
later issues depend on, and the head invariant that motivated putting all of Phase 0 in one
revision.

**Postgres and MySQL.** Every test here runs against SQLite, and against PostgreSQL and MySQL too
when ``MLFLOW_OIDC_TEST_POSTGRES_URI`` and ``MLFLOW_OIDC_TEST_MYSQL_URI`` are set (skipped otherwise,
so the default suite stays dependency-free). CI sets both — a migration verified on one backend is
verified on one backend. MySQL is where this revision broke (#494): ``groups`` is a reserved word
in MySQL 8 (raw SQL here names it through ``sql()``), and MySQL commits each DDL statement on its
own, so a failure part-way left the revision half-applied.

Run locally with, for example::

    MLFLOW_OIDC_TEST_POSTGRES_URI=postgresql+psycopg2://user@127.0.0.1:5432/test \\
    MLFLOW_OIDC_TEST_MYSQL_URI=mysql+pymysql://user:password@127.0.0.1:3306/test \\
        pytest mlflow_oidc_auth/tests/db/test_phase0_migration.py
"""

import io
import os

import pytest
from alembic import op
from alembic.command import downgrade, upgrade
from alembic.script import ScriptDirectory
from sqlalchemy import TextClause, create_engine, inspect, text
from sqlalchemy.sql.dml import Update

from mlflow_oidc_auth.db.utils import _get_alembic_config

PREVIOUS_REVISION = "8a9b0c1de234"
PHASE0_REVISION = "9c0d1e2f3456"

POSTGRES_URI = os.environ.get("MLFLOW_OIDC_TEST_POSTGRES_URI")
MYSQL_URI = os.environ.get("MLFLOW_OIDC_TEST_MYSQL_URI")


def _sqlite_uri(tmp_path) -> str:
    return f"sqlite:///{tmp_path / 'auth.db'}"


@pytest.fixture(params=["sqlite", "postgres", "mysql"])
def db_uri(request, tmp_path):
    """A database URI per backend. Postgres and MySQL cases skip unless a server is configured.

    Shared by the other migration test modules, so every revision's upgrade and downgrade is
    verified on all three.
    """
    if request.param == "sqlite":
        return _sqlite_uri(tmp_path)
    if request.param == "mysql":
        if not MYSQL_URI:
            pytest.skip("MLFLOW_OIDC_TEST_MYSQL_URI is not set")
        return MYSQL_URI
    if not POSTGRES_URI:
        pytest.skip("MLFLOW_OIDC_TEST_POSTGRES_URI is not set")
    return POSTGRES_URI


def sql(bind, statement: str) -> TextClause:
    """``text(statement)`` with ``{groups}`` replaced by the ``groups`` table, quoted for the bind's dialect.

    ``groups`` is a reserved word in MySQL 8 (#494), so raw SQL that names the table must quote it,
    and each backend quotes differently. ``bind`` is a connection or a session.
    """
    dialect = bind.dialect if hasattr(bind, "dialect") else bind.get_bind().dialect
    return text(statement.replace("{groups}", dialect.identifier_preparer.quote("groups")))


def _clean_engine(db_uri):
    """An engine on an emptied database. Refuses any database whose name does not mark it as a test one."""
    eng = create_engine(db_uri)
    if eng.dialect.name != "sqlite" and "test" not in (eng.url.database or "").lower():
        eng.dispose()
        pytest.fail(f"refusing to empty database {eng.url.database!r}: these tests drop everything in it; use a database named for tests")
    if eng.dialect.name == "postgresql":
        # Start from a clean slate: the migration chain owns the public schema for this run.
        with eng.begin() as conn:
            conn.execute(text("DROP SCHEMA public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
    elif eng.dialect.name == "mysql":
        # Same clean slate: the test database is recreated, so nothing survives between tests.
        database = eng.url.database
        with eng.begin() as conn:
            conn.execute(text(f"DROP DATABASE IF EXISTS `{database}`"))
            conn.execute(text(f"CREATE DATABASE `{database}`"))
        eng.dispose()
    yield eng
    eng.dispose()


@pytest.fixture
def engine(db_uri):
    yield from _clean_engine(db_uri)


def _alembic_config(engine):
    """An Alembic config for the embedded path, the way ``db/utils.py`` builds one.

    These tests used to clear ``config_file_name`` here, because ``env.py`` called
    ``fileConfig()`` with its ``disable_existing_loggers=True`` default and silenced loggers
    created earlier in the session — unrelated tests lost their ``caplog`` records. ``env.py``
    now skips that whenever Alembic is embedded (#342), so the workaround is gone and the tests
    exercise the same configuration the application uses.
    """
    return _get_alembic_config(engine.url.render_as_string(hide_password=False))


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
    would not reproduce a pre-migration database. ``groups`` is quoted for the backend, since it
    is a reserved word in MySQL.
    """
    groups = engine.dialect.identifier_preparer.quote("groups")
    with engine.begin() as conn:
        for i, name in enumerate(["alice@example.com", "bob@example.com", "svc@example.com"], start=1):
            conn.execute(
                text("INSERT INTO users (username, display_name, password_hash, is_admin, is_service_account) " "VALUES (:u, :d, :h, :a, :s)"),
                {"u": name, "d": name, "h": "not-a-real-hash", "a": i == 1, "s": i == 3},
            )
        conn.execute(text(f"INSERT INTO {groups} (group_name) VALUES ('legacy-team')"))
        conn.execute(
            text(f"INSERT INTO user_groups (user_id, group_id) SELECT users.id, {groups}.id FROM users, {groups} WHERE {groups}.group_name = 'legacy-team'")
        )


class TestRevisionChain:
    def test_exactly_one_head(self, tmp_path):
        """The invariant that put all of Phase 0 in one revision.

        Three parallel revisions off the same parent would give three heads and make
        ``alembic upgrade head`` fail outright for every deployment. Later revisions (the SCIM
        token table, #321) chain on Phase 0, so the head moves but must stay single and must
        descend from it.
        """
        cfg = _get_alembic_config(_sqlite_uri(tmp_path))
        script = ScriptDirectory.from_config(cfg)
        heads = script.get_heads()

        assert len(heads) == 1, f"expected a single head, got {heads}"
        assert PHASE0_REVISION in {rev.revision for rev in script.iterate_revisions(heads[0], "base")}

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

        _downgrade(engine, PREVIOUS_REVISION)

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

        _downgrade(engine, PREVIOUS_REVISION)
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
                    text("INSERT INTO users (username, display_name, active, managed_by) VALUES (:u, :u, :a, 'manual')"),
                    {"u": name, "a": True},
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
                    "INSERT INTO users (username, display_name, active, managed_by, external_id) " "VALUES ('e1@example.com', 'e1', :a, 'manual', 'shared-id')"
                ),
                {"a": True},
            )

        with pytest.raises(IntegrityError):
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "INSERT INTO users (username, display_name, active, managed_by, external_id) "
                        "VALUES ('e2@example.com', 'e2', :a, 'manual', 'shared-id')"
                    ),
                    {"a": True},
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


def test_backfill_quotes_the_groups_table_for_mysql():
    """``groups`` is reserved in MySQL 8, so the backfill must quote it (#494).

    Rendered in offline mode, which needs no MySQL server or driver.
    """
    cfg = _get_alembic_config("mysql://user@localhost/auth")
    cfg.output_buffer = io.StringIO()
    upgrade(cfg, f"{PREVIOUS_REVISION}:{PHASE0_REVISION}", sql=True)
    sql = cfg.output_buffer.getvalue()

    assert "UPDATE `groups` SET" in sql
    assert "UPDATE groups " not in sql


def _version_table() -> str:
    from mlflow_oidc_auth.config import config as app_config

    return app_config.OIDC_ALEMBIC_VERSION_TABLE


class TestResumeAfterPartialRun:
    """A run that failed part-way must be able to finish on the next start (#494).

    MySQL commits every DDL statement on its own, and Alembic's SQLite runs DDL outside the
    migration's transaction too, so on both a failed run leaves this revision's tables and columns
    in place while the version table still names the previous revision: the failure tests
    exercise the resume path there. PostgreSQL rolls the whole revision back, so on it they check
    that the resumable operations change nothing about a clean retry.
    """

    @staticmethod
    def _fail_on(monkeypatch, name: str, predicate):
        """Make ``op.<name>`` raise for the first call ``predicate`` accepts."""
        real = getattr(op, name)

        def wrapper(*args, **kwargs):
            if predicate(*args, **kwargs):
                raise RuntimeError("simulated failure")
            return real(*args, **kwargs)

        monkeypatch.setattr(op, name, wrapper)

    def test_upgrade_over_existing_data(self, engine):
        """The #494 path itself: an existing database with users and groups, upgraded to head."""
        _upgrade(engine, PREVIOUS_REVISION)
        _seed_legacy_data(engine)

        _upgrade(engine, "head")

        groups = engine.dialect.identifier_preparer.quote("groups")
        with engine.connect() as conn:
            assert conn.execute(text("SELECT count(*) FROM user_identities WHERE provider_id = 'default'")).scalar() == 3
            assert conn.execute(text("SELECT count(*) FROM users WHERE created_at IS NULL OR updated_at IS NULL")).scalar() == 0
            assert conn.execute(text(f"SELECT count(*) FROM {groups} WHERE created_at IS NULL OR updated_at IS NULL")).scalar() == 0

    def test_upgrade_finishes_after_a_failed_backfill(self, engine, monkeypatch):
        _upgrade(engine, PREVIOUS_REVISION)
        _seed_legacy_data(engine)
        with monkeypatch.context() as patched:
            # The first timestamp UPDATE, after every DDL statement has already run.
            self._fail_on(patched, "execute", lambda statement, *a, **k: isinstance(statement, Update))
            with pytest.raises(RuntimeError, match="simulated failure"):
                _upgrade(engine, "head")

        _upgrade(engine, "head")

        groups = engine.dialect.identifier_preparer.quote("groups")
        with engine.connect() as conn:
            assert conn.execute(text("SELECT count(*) FROM user_identities WHERE provider_id = 'default'")).scalar() == 3
            assert conn.execute(text("SELECT count(*) FROM users WHERE created_at IS NULL OR updated_at IS NULL")).scalar() == 0
            assert conn.execute(text(f"SELECT count(*) FROM {groups} WHERE created_at IS NULL OR updated_at IS NULL")).scalar() == 0

    def test_replay_finishes_a_partial_backfill_without_duplicating_it(self, engine):
        """The worst case of a partial run: every object exists and part of the backfill landed."""
        _upgrade(engine, PREVIOUS_REVISION)
        _seed_legacy_data(engine)
        _upgrade(engine, PHASE0_REVISION)
        with engine.begin() as conn:
            # Back to the state a crash part-way through the backfill would leave.
            conn.execute(text("DELETE FROM user_identities WHERE subject <> 'alice@example.com'"))
            conn.execute(text("UPDATE users SET created_at = NULL, updated_at = NULL WHERE username = 'bob@example.com'"))
            conn.execute(text("UPDATE users SET updated_at = NULL WHERE username = 'svc@example.com'"))
            conn.execute(text(f"UPDATE {_version_table()} SET version_num = :rev"), {"rev": PREVIOUS_REVISION})
            alice_created = conn.execute(text("SELECT created_at FROM users WHERE username = 'alice@example.com'")).scalar()

        _upgrade(engine, "head")

        with engine.connect() as conn:
            subjects = sorted(r[0] for r in conn.execute(text("SELECT subject FROM user_identities WHERE provider_id = 'default'")))
            assert subjects == ["alice@example.com", "bob@example.com", "svc@example.com"]
            assert conn.execute(text("SELECT count(*) FROM users WHERE created_at IS NULL OR updated_at IS NULL")).scalar() == 0
            assert conn.execute(text("SELECT created_at FROM users WHERE username = 'alice@example.com'")).scalar() == alice_created

    def test_replay_refuses_an_index_of_a_different_shape(self, engine):
        """An existing object is trusted by name only when its shape matches: never record a wrong schema as applied."""
        _upgrade(engine, PREVIOUS_REVISION)
        with engine.begin() as conn:
            # A non-unique index under the name this revision gives its unique one.
            conn.execute(text("ALTER TABLE users ADD COLUMN external_id VARCHAR(255)"))
            conn.execute(text("CREATE INDEX ix_users_external_id ON users (external_id)"))

        with pytest.raises(RuntimeError, match="ix_users_external_id"):
            _upgrade(engine, PHASE0_REVISION)

        with engine.connect() as conn:
            assert conn.execute(text(f"SELECT version_num FROM {_version_table()}")).scalar() == PREVIOUS_REVISION

    @pytest.mark.parametrize(
        "repair",
        [
            # user_identities without its (provider_id, subject) uniqueness: two users could share an identity.
            "CREATE TABLE user_identities (id INTEGER PRIMARY KEY, provider_id VARCHAR(255) NOT NULL, subject VARCHAR(255) NOT NULL, "
            "user_id INTEGER NOT NULL, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, last_login_at TIMESTAMP NULL)",
            # users.active nullable: a NULL would be read as neither active nor inactive.
            "ALTER TABLE users ADD COLUMN active BOOLEAN NULL",
        ],
        ids=["identity-without-unique-subject", "nullable-active"],
    )
    def test_replay_refuses_a_hand_repaired_schema_that_is_weaker(self, engine, repair):
        _upgrade(engine, PREVIOUS_REVISION)
        with engine.begin() as conn:
            conn.execute(text(repair))

        with pytest.raises(RuntimeError, match="refusing to record this revision as applied"):
            _upgrade(engine, PHASE0_REVISION)

        with engine.connect() as conn:
            assert conn.execute(text(f"SELECT version_num FROM {_version_table()}")).scalar() == PREVIOUS_REVISION

    def test_phase0_round_trip(self, engine):
        """This revision's own downgrade, on every backend (#494 made MySQL one of them)."""
        _upgrade(engine, PREVIOUS_REVISION)
        _seed_legacy_data(engine)
        _upgrade(engine, PHASE0_REVISION)

        _downgrade(engine, PREVIOUS_REVISION)

        inspector = inspect(engine)
        assert not ({"user_identities", "auth_sessions", "auth_state"} & set(inspector.get_table_names()))
        assert not ({"active", "managed_by", "external_id", "created_at", "updated_at"} & {c["name"] for c in inspector.get_columns("users")})

        _upgrade(engine, PHASE0_REVISION)

        with engine.connect() as conn:
            assert conn.execute(text("SELECT count(*) FROM user_identities")).scalar() == 3

    def test_downgrade_finishes_after_an_interrupted_run(self, engine, monkeypatch):
        _upgrade(engine, PREVIOUS_REVISION)
        _seed_legacy_data(engine)
        _upgrade(engine, PHASE0_REVISION)
        with monkeypatch.context() as patched:
            # Part-way: the groups and user_groups columns are gone, the users ones not yet.
            self._fail_on(patched, "drop_column", lambda table, column, *a, **k: table == "users")
            with pytest.raises(RuntimeError, match="simulated failure"):
                _downgrade(engine, PREVIOUS_REVISION)

        _downgrade(engine, PREVIOUS_REVISION)

        inspector = inspect(engine)
        assert not ({"user_identities", "auth_sessions", "auth_state"} & set(inspector.get_table_names()))
        assert "managed_by" not in {c["name"] for c in inspector.get_columns("user_groups")}
        with engine.connect() as conn:
            assert conn.execute(text(f"SELECT version_num FROM {_version_table()}")).scalar() == PREVIOUS_REVISION
