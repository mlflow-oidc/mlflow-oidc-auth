"""add user tokens

Revision ID: a1b2c3d4e5f6
Revises: 3c3272527ade
Create Date: 2026-01-21 12:00:00.000000

"""

from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "3c3272527ade"
branch_labels = None
depends_on = None

# Name for migrated legacy tokens
LEGACY_TOKEN_NAME = "default"


def upgrade() -> None:
    # Create the new user_tokens table
    op.create_table(
        "user_tokens",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("token_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
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
    for user in users:
        user_id, password_hash, password_expiration = user
        if password_hash:
            connection.execute(
                user_tokens_table.insert().values(
                    user_id=user_id,
                    name=LEGACY_TOKEN_NAME,
                    token_hash=password_hash,
                    created_at=now,
                    expires_at=password_expiration,
                )
            )

    # NOTE: We intentionally do NOT drop the password_hash and password_expiration
    # columns from the users table in this migration. This allows for safe rollback
    # if needed. A future migration will remove these deprecated columns once the
    # multi-token system has been stable for a release cycle.


def downgrade() -> None:
    # Restore the "default" tokens back to users.password_hash for rollback
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
