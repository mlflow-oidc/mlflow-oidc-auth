"""add user tokens

Revision ID: a1b2c3d4e5f6
Revises: 3c3272527ade
Create Date: 2026-01-21 12:00:00.000000

"""

from datetime import datetime, timedelta, timezone

import sqlalchemy as sa
from alembic import op

from mlflow_oidc_auth.constants import DEFAULT_TOKEN_NAME

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "6a7b8c9def01"
branch_labels = None
depends_on = None

# Alias for clarity in migration context
LEGACY_TOKEN_NAME = DEFAULT_TOKEN_NAME


def upgrade() -> None:
    # Create the new user_tokens table
    op.create_table(
        "user_tokens",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("token_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_user_token_user_id"),
        sa.UniqueConstraint("user_id", "name", name="unique_user_token_name"),
    )

    # Migrate existing password_hash tokens to the new table
    # This preserves backwards compatibility for existing users
    connection = op.get_bind()
    users_table = sa.table(
        "users",
        sa.column("id", sa.Integer),
        sa.column("password_hash", sa.String),
        sa.column("password_expiration", sa.DateTime),
    )
    user_tokens_table = sa.table(
        "user_tokens",
        sa.column("user_id", sa.Integer),
        sa.column("name", sa.String),
        sa.column("token_hash", sa.String),
        sa.column("created_at", sa.DateTime),
        sa.column("expires_at", sa.DateTime),
    )

    # Select all users with a password_hash
    users = connection.execute(sa.select(users_table.c.id, users_table.c.password_hash, users_table.c.password_expiration)).fetchall()

    now = datetime.now(timezone.utc)
    default_expiration = now + timedelta(days=365)  # 1 year from migration date
    for user in users:
        user_id, password_hash, password_expiration = user
        if password_hash:
            # Use existing expiration or default to 1 year from migration
            expiration = password_expiration if password_expiration is not None else default_expiration
            connection.execute(
                user_tokens_table.insert().values(
                    user_id=user_id,
                    name=LEGACY_TOKEN_NAME,
                    token_hash=password_hash,
                    created_at=now,
                    expires_at=expiration,
                )
            )

    # Drop the old columns - all authentication now goes through user_tokens
    # Note: SQLite doesn't support DROP COLUMN, so we handle it differently
    dialect = connection.dialect.name

    if dialect == "sqlite":
        # For SQLite, recreate the table without the columns
        op.execute("""
            CREATE TABLE users_new (
                id INTEGER NOT NULL PRIMARY KEY,
                username VARCHAR(255) UNIQUE,
                display_name VARCHAR(255) NOT NULL,
                is_admin BOOLEAN DEFAULT 0,
                is_service_account BOOLEAN DEFAULT 0
            )
            """)

        # Copy data to the new table
        op.execute("""
            INSERT INTO users_new (id, username, display_name, is_admin, is_service_account)
            SELECT id, username, display_name, is_admin, is_service_account FROM users
            """)

        # Drop the old table and rename the new one
        op.execute("DROP TABLE users")
        op.execute("ALTER TABLE users_new RENAME TO users")
    else:
        # For other databases (PostgreSQL, MySQL), use standard ALTER TABLE
        op.drop_column("users", "password_hash")
        op.drop_column("users", "password_expiration")


def downgrade() -> None:
    # Restore the "default" tokens back to users.password_hash for rollback
    connection = op.get_bind()
    dialect = connection.dialect.name

    # Check for non-default tokens that would be lost
    non_default_count = connection.execute(sa.text("SELECT COUNT(*) FROM user_tokens WHERE name != :name").bindparams(name=LEGACY_TOKEN_NAME)).scalar()
    if non_default_count > 0:
        raise RuntimeError(
            f"Cannot rollback: {non_default_count} non-default token(s) would be lost. "
            "Delete these tokens manually before downgrading, or backup the user_tokens table."
        )

    if dialect == "sqlite":
        # For SQLite, recreate the table with the columns
        op.execute("""
            CREATE TABLE users_new (
                id INTEGER NOT NULL PRIMARY KEY,
                username VARCHAR(255) UNIQUE,
                display_name VARCHAR(255) NOT NULL,
                password_hash VARCHAR(255) NOT NULL DEFAULT '',
                password_expiration DATETIME,
                is_admin BOOLEAN DEFAULT 0,
                is_service_account BOOLEAN DEFAULT 0
            )
            """)

        # Copy data back
        op.execute("""
            INSERT INTO users_new (id, username, display_name, is_admin, is_service_account, password_hash)
            SELECT id, username, display_name, is_admin, is_service_account, '' FROM users
            """)

        # Update password_hash and password_expiration from user_tokens where name='default'
        op.execute(f"""
            UPDATE users_new SET
                password_hash = COALESCE((SELECT token_hash FROM user_tokens WHERE user_tokens.user_id = users_new.id AND user_tokens.name = '{LEGACY_TOKEN_NAME}'), ''),
                password_expiration = (SELECT expires_at FROM user_tokens WHERE user_tokens.user_id = users_new.id AND user_tokens.name = '{LEGACY_TOKEN_NAME}')
            """)

        # Drop the old table and rename the new one
        op.execute("DROP TABLE users")
        op.execute("ALTER TABLE users_new RENAME TO users")
    else:
        # For other databases, add columns back
        op.add_column("users", sa.Column("password_hash", sa.String(length=255), nullable=False, server_default=""))
        op.add_column("users", sa.Column("password_expiration", sa.DateTime(), nullable=True))

        users_table = sa.table(
            "users",
            sa.column("id", sa.Integer),
            sa.column("password_hash", sa.String),
            sa.column("password_expiration", sa.DateTime),
        )
        user_tokens_table = sa.table(
            "user_tokens",
            sa.column("user_id", sa.Integer),
            sa.column("name", sa.String),
            sa.column("token_hash", sa.String),
            sa.column("expires_at", sa.DateTime),
        )

        # Get the "default" token for each user (these were the migrated legacy tokens)
        default_tokens = connection.execute(
            sa.select(
                user_tokens_table.c.user_id,
                user_tokens_table.c.token_hash,
                user_tokens_table.c.expires_at,
            ).where(user_tokens_table.c.name == LEGACY_TOKEN_NAME)
        ).fetchall()

        # Restore each default token back to the users table
        for token in default_tokens:
            user_id, token_hash, expires_at = token
            connection.execute(users_table.update().where(users_table.c.id == user_id).values(password_hash=token_hash, password_expiration=expires_at))

    op.drop_table("user_tokens")
