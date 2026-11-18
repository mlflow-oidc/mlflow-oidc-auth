"""phase0 identity, sessions and lifecycle schema

Revision ID: 9c0d1e2f3456
Revises: 8a9b0c1de234
Create Date: 2026-08-09 00:00:00.000000

All Phase 0 schema for the enterprise-identity epic (#304) lands in this single revision
(issue #333). Splitting it across #309, #310 and #311 would give each its own revision off
``8a9b0c1de234``, producing three Alembic heads and breaking ``alembic upgrade head`` outright.
With the schema here, those three can proceed in parallel on behaviour alone.

Schema and backfill only — no behaviour. Identity resolution (#309), session handling (#310),
``active`` enforcement (#311) and the ``managed_by`` write guard (#319) all come later.

Two backfill choices are load-bearing and are asserted by tests:

* Pre-existing rows are labelled ``managed_by='manual'``, never ``'oidc:default'``. Existing
  group memberships were not necessarily claim-derived, and mislabelling them would let the
  #319 guard refuse admin edits to memberships that were in fact manual — up to locking every
  admin out of their own permission data, which needs out-of-band access to recover from.
* ``users.active`` is NOT NULL with a true default, so no existing user is denied at their next
  login once #311 starts enforcing it.
"""

import sqlalchemy as sa
from alembic import op

from mlflow_oidc_auth.db.migrations.resumable import ResumableSchema

# revision identifiers, used by Alembic.
revision = "9c0d1e2f3456"
down_revision = "8a9b0c1de234"
branch_labels = None
depends_on = None

# The identity provider that pre-existing users are attributed to. Their subject is their
# username, which is what every current lookup already keys on.
LEGACY_PROVIDER_ID = "default"

# Rows that predate provisioning are manual by definition: nothing external created them.
MANUAL = "manual"


# Tables whose timestamps the backfill fills. Lightweight table objects rather than raw SQL so
# each backend quotes the names: ``groups`` is a reserved word in MySQL 8, where an unquoted
# ``UPDATE groups ...`` is a syntax error (#494).
_TIMESTAMPED_TABLES = (
    sa.table("users", sa.column("created_at"), sa.column("updated_at")),
    sa.table("groups", sa.column("created_at"), sa.column("updated_at")),
)


def upgrade() -> None:
    # Resumable: a run interrupted on MySQL or SQLite, where the DDL below is not rolled back,
    # leaves its objects behind, and the next start replays this revision (#494).
    schema = ResumableSchema(revision)
    create_table, create_index, add_column = schema.create_table, schema.create_index, schema.add_column

    # --- identity (#309) -------------------------------------------------------------------
    create_table(
        "user_identities",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("provider_id", sa.String(length=255), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_user_identities_user_id"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_id", "subject", name="uq_user_identities_provider_subject"),
    )
    create_index("ix_user_identities_user_id", "user_identities", ["user_id"])

    # --- sessions (#310) -------------------------------------------------------------------
    create_table(
        "auth_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        # Opaque 256-bit identifier. Sized for either encoding a caller may choose (64 hex
        # characters, 43 base64url) with room to spare.
        sa.Column("session_id", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("provider_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        # Encrypted at the application layer before it reaches this column; the schema only
        # promises somewhere to put it. Text rather than String because provider token sets
        # have no useful length bound.
        sa.Column("encrypted_tokens", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_auth_sessions_user_id"),
        sa.PrimaryKeyConstraint("id"),
    )
    create_index("ix_auth_sessions_session_id", "auth_sessions", ["session_id"], unique=True)
    create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    # Revocation sweeps and expiry sweeps both scan by expiry.
    create_index("ix_auth_sessions_expires_at", "auth_sessions", ["expires_at"])

    # --- in-flight authorization state (#310) ----------------------------------------------
    create_table(
        "auth_state",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("state", sa.String(length=255), nullable=False),
        sa.Column("nonce", sa.String(length=255), nullable=True),
        sa.Column("code_verifier", sa.String(length=255), nullable=True),
        sa.Column("provider_id", sa.String(length=255), nullable=True),
        sa.Column("relay_state", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    create_index("ix_auth_state_state", "auth_state", ["state"], unique=True)
    # These rows are short-lived and swept in bulk.
    create_index("ix_auth_state_expires_at", "auth_state", ["expires_at"])

    # --- lifecycle columns (#311) ----------------------------------------------------------
    # server_default populates existing rows in the same statement, so there is no window in
    # which a row exists with no value. active is NOT NULL/true so nobody is denied later.
    add_column("users", sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()))
    add_column("users", sa.Column("managed_by", sa.String(length=255), nullable=False, server_default=MANUAL))
    add_column("users", sa.Column("external_id", sa.String(length=255), nullable=True))
    # Timestamps are added nullable and filled by an explicit UPDATE below. SQLite refuses
    # ADD COLUMN with a non-constant default (CURRENT_TIMESTAMP) — but only once the table has
    # rows, accepting it on an empty one. Declaring them NOT NULL DEFAULT now() would therefore
    # pass every fresh-install test and fail on exactly the deployments that have users.
    add_column("users", sa.Column("created_at", sa.DateTime(), nullable=True))
    add_column("users", sa.Column("updated_at", sa.DateTime(), nullable=True))
    # Unique *index* rather than a constraint: both backends allow repeated NULLs in a unique
    # index, which is what "unique when present" means here.
    create_index("ix_users_external_id", "users", ["external_id"], unique=True)

    add_column("user_groups", sa.Column("managed_by", sa.String(length=255), nullable=False, server_default=MANUAL))

    add_column("groups", sa.Column("external_id", sa.String(length=255), nullable=True))
    add_column("groups", sa.Column("created_at", sa.DateTime(), nullable=True))
    add_column("groups", sa.Column("updated_at", sa.DateTime(), nullable=True))
    create_index("ix_groups_external_id", "groups", ["external_id"], unique=True)

    # --- backfill --------------------------------------------------------------------------
    # Existing rows predate these columns, so their creation time is unknowable; the migration
    # time is the honest approximation and is recorded rather than left NULL. Each column is
    # filled only where it is still NULL, so a resumed run leaves alone what an earlier attempt
    # already wrote, and finishes what it did not.
    for target in _TIMESTAMPED_TABLES:
        for column in (target.c.created_at, target.c.updated_at):
            op.execute(target.update().where(column.is_(None)).values({column.name: sa.func.current_timestamp()}))

    # Every pre-existing user gets an identity so that identity resolution (#309) never finds a
    # stranded account. Their subject is the username, which is what today's lookups key on.
    # id is omitted so the backend assigns it, and created_at falls to its server default. Users
    # that already have a legacy identity are skipped, so a resumed run cannot hit the
    # (provider_id, subject) unique constraint.
    op.execute(sa.text("""
            INSERT INTO user_identities (provider_id, subject, user_id)
            SELECT :provider_id, users.username, users.id FROM users
            WHERE NOT EXISTS (
                SELECT 1 FROM user_identities
                WHERE user_identities.provider_id = :provider_id AND user_identities.subject = users.username
            )
            """).bindparams(provider_id=LEGACY_PROVIDER_ID))


def downgrade() -> None:
    # Resumable for the same reason as upgrade(): on MySQL and SQLite an interrupted downgrade
    # keeps what it already dropped. The indexes of the tables dropped below go with their tables;
    # dropping them first fails on MySQL for an index a foreign key relies on.
    schema = ResumableSchema(revision)

    schema.drop_index("ix_groups_external_id", "groups")
    schema.drop_column("groups", "updated_at")
    schema.drop_column("groups", "created_at")
    schema.drop_column("groups", "external_id")

    schema.drop_column("user_groups", "managed_by")

    schema.drop_index("ix_users_external_id", "users")
    schema.drop_column("users", "updated_at")
    schema.drop_column("users", "created_at")
    schema.drop_column("users", "external_id")
    schema.drop_column("users", "managed_by")
    schema.drop_column("users", "active")

    schema.drop_table("auth_state")
    schema.drop_table("auth_sessions")
    schema.drop_table("user_identities")
