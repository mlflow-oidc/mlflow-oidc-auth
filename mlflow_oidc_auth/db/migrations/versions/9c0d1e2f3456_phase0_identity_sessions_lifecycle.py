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


def upgrade() -> None:
    # --- identity (#309) -------------------------------------------------------------------
    op.create_table(
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
    op.create_index("ix_user_identities_user_id", "user_identities", ["user_id"])

    # --- sessions (#310) -------------------------------------------------------------------
    op.create_table(
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
    op.create_index("ix_auth_sessions_session_id", "auth_sessions", ["session_id"], unique=True)
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    # Revocation sweeps and expiry sweeps both scan by expiry.
    op.create_index("ix_auth_sessions_expires_at", "auth_sessions", ["expires_at"])

    # --- in-flight authorization state (#310) ----------------------------------------------
    op.create_table(
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
    op.create_index("ix_auth_state_state", "auth_state", ["state"], unique=True)
    # These rows are short-lived and swept in bulk.
    op.create_index("ix_auth_state_expires_at", "auth_state", ["expires_at"])

    # --- lifecycle columns (#311) ----------------------------------------------------------
    # server_default populates existing rows in the same statement, so there is no window in
    # which a row exists with no value. active is NOT NULL/true so nobody is denied later.
    op.add_column("users", sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("users", sa.Column("managed_by", sa.String(length=255), nullable=False, server_default=MANUAL))
    op.add_column("users", sa.Column("external_id", sa.String(length=255), nullable=True))
    # Timestamps are added nullable and filled by an explicit UPDATE below. SQLite refuses
    # ADD COLUMN with a non-constant default (CURRENT_TIMESTAMP) — but only once the table has
    # rows, accepting it on an empty one. Declaring them NOT NULL DEFAULT now() would therefore
    # pass every fresh-install test and fail on exactly the deployments that have users.
    op.add_column("users", sa.Column("created_at", sa.DateTime(), nullable=True))
    op.add_column("users", sa.Column("updated_at", sa.DateTime(), nullable=True))
    # Unique *index* rather than a constraint: both backends allow repeated NULLs in a unique
    # index, which is what "unique when present" means here.
    op.create_index("ix_users_external_id", "users", ["external_id"], unique=True)

    op.add_column("user_groups", sa.Column("managed_by", sa.String(length=255), nullable=False, server_default=MANUAL))

    op.add_column("groups", sa.Column("external_id", sa.String(length=255), nullable=True))
    op.add_column("groups", sa.Column("created_at", sa.DateTime(), nullable=True))
    op.add_column("groups", sa.Column("updated_at", sa.DateTime(), nullable=True))
    op.create_index("ix_groups_external_id", "groups", ["external_id"], unique=True)

    # --- backfill --------------------------------------------------------------------------
    # Existing rows predate these columns, so their creation time is unknowable; the migration
    # time is the honest approximation and is recorded rather than left NULL.
    for table in ("users", "groups"):
        op.execute(f"UPDATE {table} SET created_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP")  # nosec B608 - fixed literals

    # Every pre-existing user gets an identity so that identity resolution (#309) never finds a
    # stranded account. Their subject is the username, which is what today's lookups key on.
    # id is omitted so the backend assigns it, and created_at falls to its server default.
    op.execute(sa.text("""
            INSERT INTO user_identities (provider_id, subject, user_id)
            SELECT :provider_id, users.username, users.id FROM users
            """).bindparams(provider_id=LEGACY_PROVIDER_ID))


def downgrade() -> None:
    op.drop_index("ix_groups_external_id", table_name="groups")
    op.drop_column("groups", "updated_at")
    op.drop_column("groups", "created_at")
    op.drop_column("groups", "external_id")

    op.drop_column("user_groups", "managed_by")

    op.drop_index("ix_users_external_id", table_name="users")
    op.drop_column("users", "updated_at")
    op.drop_column("users", "created_at")
    op.drop_column("users", "external_id")
    op.drop_column("users", "managed_by")
    op.drop_column("users", "active")

    op.drop_index("ix_auth_state_expires_at", table_name="auth_state")
    op.drop_index("ix_auth_state_state", table_name="auth_state")
    op.drop_table("auth_state")

    op.drop_index("ix_auth_sessions_expires_at", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_user_id", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_session_id", table_name="auth_sessions")
    op.drop_table("auth_sessions")

    op.drop_index("ix_user_identities_user_id", table_name="user_identities")
    op.drop_table("user_identities")
