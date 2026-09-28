"""user tokens

Revision ID: f6a7b8c9d0e1
Revises: d3a4b5c6e7f8
Create Date: 2026-09-28 12:00:00.000000

Many named access tokens per user (issue #189), replacing the single secret in
``users.password_hash`` / ``users.password_expiration``.

Upgrade:

* creates ``user_tokens``;
* carries each user's current secret over as a token named ``default``. Its hash is copied as it
  is, so the secret keeps working unchanged. Before this revision every user was created with a
  random secret nobody was told, and it cannot be told apart from one a person was issued, so
  most users get such a ``default`` token; the UI labels carried-over tokens, and a user or an
  administrator can delete one they do not use. It has no ``token_prefix`` — the old secret carries
  none — and authentication finds it through the one prefix-less row a user may hold. A secret
  that has already expired is not carried over: it could never authenticate again.
* gives a carried-over secret that never expired an expiry one year from the migration. Tokens
  must expire; this is the one place a non-expiring one could otherwise enter the table.
* drops ``users.password_hash`` and ``users.password_expiration``.

Downgrade restores both columns and puts one token per user back in them: the ``default`` token
while it is live, otherwise the user's newest live token, otherwise the ``default`` token even if
expired. A user without any token gets an undisclosed random secret, as a user created before this
revision had. Every other token is dropped with the table; the count is logged. The downgrade
never refuses — an operator rolling back in an incident must not be blocked by data the new
version created.

``batch_alter_table`` because SQLite cannot drop a column in place: it rebuilds ``users`` from the
reflected schema, so constraints and indexes survive, and on PostgreSQL it is a plain ALTER.
"""

import secrets
from datetime import datetime, timedelta, timezone

import sqlalchemy as sa
from alembic import op
from werkzeug.security import generate_password_hash

from mlflow_oidc_auth.logger import get_logger

logger = get_logger()

# revision identifiers, used by Alembic.
revision = "f6a7b8c9d0e1"
down_revision = "d3a4b5c6e7f8"
branch_labels = None
depends_on = None

DEFAULT_TOKEN_NAME = "default"
# Pinned here rather than imported: a migration must keep doing what it did when it was written.
TOKEN_HASH_METHOD = "pbkdf2:sha256:1000"

_users = sa.table(
    "users",
    sa.column("id", sa.Integer),
    sa.column("password_hash", sa.String),
    sa.column("password_expiration", sa.DateTime),
)
_tokens = sa.table(
    "user_tokens",
    sa.column("id", sa.Integer),
    sa.column("user_id", sa.Integer),
    sa.column("name", sa.String),
    sa.column("token_prefix", sa.String),
    sa.column("token_hash", sa.String),
    sa.column("created_at", sa.DateTime),
    sa.column("created_by", sa.String),
    sa.column("expires_at", sa.DateTime),
    sa.column("last_used_at", sa.DateTime),
)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _naive_utc(value):
    if value is not None and value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def upgrade() -> None:
    op.create_table(
        "user_tokens",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("token_prefix", sa.String(length=32), nullable=True),
        sa.Column("token_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_user_tokens_user_id", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "name", name="uq_user_tokens_user_id_name"),
    )
    op.create_index("ix_user_tokens_token_prefix", "user_tokens", ["token_prefix"], unique=True)

    connection = op.get_bind()
    now = _now()
    default_expiry = now + timedelta(days=365)
    rows = []
    for user_id, password_hash, password_expiration in connection.execute(
        sa.select(_users.c.id, _users.c.password_hash, _users.c.password_expiration)
    ).fetchall():
        if not password_hash:
            continue
        expires_at = _naive_utc(password_expiration)
        if expires_at is None:
            expires_at = default_expiry
        elif expires_at <= now:
            continue
        rows.append(
            {
                "user_id": user_id,
                "name": DEFAULT_TOKEN_NAME,
                "token_prefix": None,
                "token_hash": password_hash,
                "created_at": now,
                "created_by": None,
                "expires_at": expires_at,
                "last_used_at": None,
            }
        )
    if rows:
        op.bulk_insert(_tokens, rows)
    logger.info("user_tokens: carried %d existing secret(s) over as 'default' tokens", len(rows))

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("password_expiration")
        batch_op.drop_column("password_hash")


def _pick(tokens, now):
    """The token to restore for one user: see the module docstring."""
    live = [t for t in tokens if t.expires_at > now]
    for token in live:
        if token.name == DEFAULT_TOKEN_NAME:
            return token
    if live:
        return max(live, key=lambda t: (t.created_at, t.id))
    for token in tokens:
        if token.name == DEFAULT_TOKEN_NAME:
            return token
    return None


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("password_hash", sa.String(length=255), nullable=False, server_default=""))
        batch_op.add_column(sa.Column("password_expiration", sa.DateTime(), nullable=True))

    connection = op.get_bind()
    now = _now()
    by_user = {}
    for token in connection.execute(
        sa.select(_tokens.c.id, _tokens.c.user_id, _tokens.c.name, _tokens.c.token_hash, _tokens.c.created_at, _tokens.c.expires_at)
    ).fetchall():
        by_user.setdefault(token.user_id, []).append(token)

    dropped = 0
    for (user_id,) in connection.execute(sa.select(_users.c.id)).fetchall():
        tokens = by_user.get(user_id, [])
        chosen = _pick(tokens, now)
        if chosen is None:
            values = {"password_hash": generate_password_hash(secrets.token_urlsafe(32), method=TOKEN_HASH_METHOD), "password_expiration": None}
        else:
            values = {"password_hash": chosen.token_hash, "password_expiration": chosen.expires_at}
            dropped += len(tokens) - 1
        connection.execute(_users.update().where(_users.c.id == user_id).values(**values))
    if dropped:
        logger.warning("user_tokens downgrade: %d token(s) beyond one per user were dropped and no longer authenticate", dropped)

    # The default only existed so the column could be added to a populated table; every row now
    # holds a hash, and the previous revision's column had none.
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("password_hash", existing_type=sa.String(length=255), existing_nullable=False, server_default=None)

    op.drop_index("ix_user_tokens_token_prefix", table_name="user_tokens")
    op.drop_table("user_tokens")
