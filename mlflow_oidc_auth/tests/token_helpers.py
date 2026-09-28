"""Access tokens for tests (issue #189).

A user no longer gets a secret at creation, so a test that authenticates with basic auth has to
issue one. Two ways:

* :func:`issue_token` — a real ``mlf_<prefix>_<secret>`` token through the store, what a user gets
  from the API. Prefer it.
* :func:`set_known_token` — a prefix-less ``default`` token with a secret the test chooses, exactly
  the row the migration writes for a pre-#189 secret. For suites that authenticate with a fixed
  constant; it exercises the carried-over-secret path.

Both only ever write to a test's temporary database.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from werkzeug.security import generate_password_hash


def issue_token(store, username: str, name: str = "default", days: int = 30) -> str:
    """Issue a real token for ``username`` and return its plaintext."""
    _, plaintext = store.create_user_token(username, name, datetime.now(timezone.utc) + timedelta(days=days), created_by="test")
    return plaintext


def set_known_token(store, username: str, secret: str, expires_at: Optional[datetime] = None) -> None:
    """Give ``username`` a prefix-less ``default`` token whose secret is ``secret``, replacing any.

    ``expires_at`` is naive UTC; the default is thirty days away.
    """
    from mlflow_oidc_auth.db.models import SqlUser, SqlUserToken
    from mlflow_oidc_auth.repository.user_token import TOKEN_HASH_METHOD

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    users = SqlUser.__table__
    tokens = SqlUserToken.__table__
    with store.engine.begin() as conn:
        user_id = conn.execute(users.select().where(users.c.username == username.lower())).fetchone().id
        conn.execute(tokens.delete().where(tokens.c.user_id == user_id, tokens.c.name == "default"))
        conn.execute(
            tokens.insert().values(
                user_id=user_id,
                name="default",
                token_prefix=None,
                token_hash=generate_password_hash(secret, method=TOKEN_HASH_METHOD),
                created_at=now,
                expires_at=expires_at if expires_at is not None else now + timedelta(days=30),
            )
        )
