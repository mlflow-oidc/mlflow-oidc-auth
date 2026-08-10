from datetime import datetime, timezone
from typing import Callable, List, Optional

from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import (
    RESOURCE_ALREADY_EXISTS,
    RESOURCE_DOES_NOT_EXIST,
)
from mlflow.utils.validation import _validate_username
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import load_only, noload, selectinload
from sqlalchemy.orm import Session
from werkzeug.security import check_password_hash, generate_password_hash

from mlflow_oidc_auth.db.models import SqlGroup, SqlUser
from mlflow_oidc_auth.entities import User
from mlflow_oidc_auth.repository.utils import get_user

# Hash method for secrets stored in ``users.password_hash`` (issue #336).
#
# Nothing in this plugin stores a human-chosen password. Every value written here comes from
# ``mlflow_oidc_auth.user.generate_token()`` — 24 characters drawn by ``secrets.choice`` from a
# 62-character alphabet, about 143 bits of entropy — and no endpoint accepts an operator-supplied
# password. A memory-hard KDF exists to make brute-forcing *low-entropy* human passwords
# expensive; against 143 bits there is nothing to brute-force, so the ~48 ms that Werkzeug's
# default scrypt costs bought no security while being paid on every basic-authenticated request.
# Verification drops from ~47 ms to ~0.08 ms.
#
# Migration is handled by Werkzeug itself: the method is encoded in the stored hash and
# ``check_password_hash`` dispatches on it, so hashes written before this change keep verifying
# under scrypt, unchanged. Only newly written hashes use this method — a secret moves over when
# its token is rotated. Existing hashes are deliberately never re-hashed in place: a stored
# secret cannot be distinguished from a hypothetical operator-set password, and silently
# re-hashing one at this cost factor would weaken it.
#
# This is intentionally a constant, not configuration. It is a property of what we store, not a
# deployment choice, and the failure mode of setting it wrong is silent.
#
# The entropy premise is not self-enforcing: ``generate_token()`` lives in another module, and
# shortening it or narrowing its alphabet would make this cost factor indefensible without
# anything here changing. ``TestTokenEntropyPremise`` in
# ``tests/repository/test_user_token_hashing.py`` pins the token's length, alphabet and resulting
# entropy, so that change fails a test instead of passing quietly. If one of those tests has to
# be updated, this constant has to be re-justified in the same diff.
TOKEN_HASH_METHOD = "pbkdf2:sha256:1000"


def normalize_username(username: str) -> str:
    """Fold a username to its canonical (lowercase) form.

    Usernames are case-insensitive identity keys — emails, or admin-chosen
    service-account names. OIDC providers may return an email in mixed case
    (issue #145) and admins may create service accounts with capitals
    (issue #219). Normalizing to lowercase at the store boundary keeps creation
    and every lookup (OIDC, basic, bearer, token) consistent, so a user can
    authenticate regardless of the case they or the IdP present. Only the
    identity key is folded; the human-readable ``display_name`` is left intact.
    """
    return username.lower() if isinstance(username, str) else username


class UserRepository:
    def __init__(self, session_maker):
        self._Session: Callable[[], Session] = session_maker

    def create(
        self,
        username: str,
        password: str,
        display_name: str,
        is_admin: bool = False,
        is_service_account: bool = False,
    ) -> User:
        username = normalize_username(username)
        _validate_username(username)
        pwhash = generate_password_hash(password, method=TOKEN_HASH_METHOD)
        with self._Session(read_only=False) as session:
            try:
                u = SqlUser(
                    username=username,
                    password_hash=pwhash,
                    display_name=display_name,
                    is_admin=is_admin,
                    is_service_account=is_service_account,
                )
                session.add(u)
                session.flush()
                return u.to_mlflow_entity()
            except IntegrityError as e:
                raise MlflowException(f"User '{username}' already exists: {e}", RESOURCE_ALREADY_EXISTS) from e

    def get(self, username: str) -> User:
        username = normalize_username(username)
        with self._Session() as session:
            u = session.query(SqlUser).filter(SqlUser.username == username).one_or_none()
            if u is None:
                raise MlflowException(f"User '{username}' not found", RESOURCE_DOES_NOT_EXIST)
            return u.to_mlflow_entity()

    def get_profile(self, username: str) -> User:
        """Fetch a lightweight user entity without loading permission relationships.

        This is intended for common operations (e.g. "who am I" and admin checks)
        where loading experiment/model/scorer permission collections would be
        unnecessarily expensive.

        Returns:
            User: A User entity with groups populated and permission lists empty.

        Raises:
            MlflowException: If the user does not exist.
        """

        username = normalize_username(username)
        with self._Session() as session:
            u = (
                session.query(SqlUser)
                .options(
                    load_only(
                        SqlUser.id,
                        SqlUser.username,
                        SqlUser.display_name,
                        SqlUser.password_expiration,
                        SqlUser.is_admin,
                        SqlUser.is_service_account,
                        # Widening the existing select rather than adding a query: this row is
                        # already fetched on every authenticated request, so #311 and #319 get
                        # these for free and the #305 budget of 2 statements is unchanged.
                        SqlUser.active,
                        SqlUser.managed_by,
                    ),
                    selectinload(SqlUser.groups).load_only(SqlGroup.id, SqlGroup.group_name),
                    noload(SqlUser.experiment_permissions),
                    noload(SqlUser.registered_model_permissions),
                    noload(SqlUser.scorer_permissions),
                    noload(SqlUser.gateway_endpoint_permissions),
                    noload(SqlUser.gateway_model_definition_permissions),
                    noload(SqlUser.gateway_secret_permissions),
                )
                .filter(SqlUser.username == username)
                .one_or_none()
            )
            if u is None:
                raise MlflowException(f"User '{username}' not found", RESOURCE_DOES_NOT_EXIST)

            return User(
                id_=u.id,
                username=u.username,
                display_name=u.display_name,
                password_hash="REDACTED",
                password_expiration=u.password_expiration,
                is_admin=u.is_admin,
                is_service_account=u.is_service_account,
                experiment_permissions=[],
                registered_model_permissions=[],
                scorer_permissions=[],
                groups=[g.to_mlflow_entity() for g in u.groups],
            )

    def exist(self, username: str) -> bool:
        username = normalize_username(username)
        with self._Session() as session:
            return session.query(SqlUser).filter(SqlUser.username == username).first() is not None

    def list(self, is_service_account: bool = False, all: bool = False) -> List[User]:
        with self._Session() as session:
            q = session.query(SqlUser)
            if not all:
                q = q.filter(SqlUser.is_service_account == is_service_account)
            return [u.to_mlflow_entity() for u in q.all()]

    def list_usernames(self, is_service_account: bool = False) -> List[str]:
        """Return only usernames without loading any relationships.

        This is much cheaper than ``list()`` because it avoids loading
        experiment/model/scorer/gateway permission collections and groups
        for every user row.
        """
        with self._Session() as session:
            rows = session.query(SqlUser.username).filter(SqlUser.is_service_account == is_service_account).all()
            return [r[0] for r in rows]

    def update(
        self,
        username: str,
        password: Optional[str] = None,
        password_expiration: Optional[datetime] = None,
        is_admin: Optional[bool] = None,
        is_service_account: Optional[bool] = None,
    ) -> User:
        """Update the supplied fields of a user, leaving omitted ones untouched.

        ``None`` means "not supplied" for every parameter but one: the corresponding column is
        left as it is. The defaults for the two flags previously read ``False`` while the guards
        below tested for ``None``, so a caller that omitted them silently cleared ``is_admin``
        and ``is_service_account`` instead of preserving them (issue #338).

        The exception is ``password_expiration``, because expiry is a property of the *secret*
        rather than of the user:

        * When ``password`` is supplied, the secret is being replaced, so it gets a fresh
          lifetime — exactly the one passed in, with ``None`` meaning "does not expire". The
          previous value is never inherited. Inheriting it meant that rotating an already-expired
          token produced a new token that was rejected on its first use, because ``authenticate``
          checks expiry before comparing the hash.
        * When ``password`` is not supplied, the expiry is only changed if one was passed.

        A consequence worth stating: an expiry cannot be cleared without also rotating the
        secret. That is deliberate — extending the life of a credential that has already been
        issued should require issuing a new one.

        Parameters:
            username: Identity key of the user to update.
            password: New secret. Hashed with :data:`TOKEN_HASH_METHOD`.
            password_expiration: Expiry for the stored secret. See the semantics above.
            is_admin: New administrator flag.
            is_service_account: New service-account flag.

        Returns:
            User: The updated user entity.

        Raises:
            MlflowException: If the user does not exist.
        """
        from werkzeug.security import generate_password_hash

        username = normalize_username(username)
        with self._Session(read_only=False) as session:
            user = get_user(session, username)
            if password is not None:
                user.password_hash = generate_password_hash(password, method=TOKEN_HASH_METHOD)
                # A new secret gets the lifetime it was issued with, never the old one's.
                user.password_expiration = password_expiration
            elif password_expiration is not None:
                user.password_expiration = password_expiration
            if is_admin is not None:
                user.is_admin = is_admin
            if is_service_account is not None:
                user.is_service_account = is_service_account
            session.flush()
            return user.to_mlflow_entity()

    def delete(self, username: str) -> None:
        username = normalize_username(username)
        with self._Session(read_only=False) as session:
            user = get_user(session, username)
            if user is None:
                raise MlflowException(f"User '{username}' not found.")

            # Delete dependent rows first.
            # Without this, SQLAlchemy may try to NULL-out non-nullable FKs
            # (e.g. experiment_permissions.user_id), causing IntegrityError.
            from mlflow_oidc_auth.db.models import (
                SqlExperimentPermission,
                SqlExperimentRegexPermission,
                SqlGatewayEndpointPermission,
                SqlGatewayEndpointRegexPermission,
                SqlGatewayModelDefinitionPermission,
                SqlGatewayModelDefinitionRegexPermission,
                SqlGatewaySecretPermission,
                SqlGatewaySecretRegexPermission,
                SqlRegisteredModelPermission,
                SqlRegisteredModelRegexPermission,
                SqlScorerPermission,
                SqlScorerRegexPermission,
                SqlUserGroup,
                SqlWorkspacePermission,
                SqlWorkspaceRegexPermission,
            )

            user_id = user.id

            # Experiment permissions
            session.query(SqlExperimentPermission).filter(SqlExperimentPermission.user_id == user_id).delete(synchronize_session=False)
            session.query(SqlExperimentRegexPermission).filter(SqlExperimentRegexPermission.user_id == user_id).delete(synchronize_session=False)

            # Registered model permissions
            session.query(SqlRegisteredModelPermission).filter(SqlRegisteredModelPermission.user_id == user_id).delete(synchronize_session=False)
            session.query(SqlRegisteredModelRegexPermission).filter(SqlRegisteredModelRegexPermission.user_id == user_id).delete(synchronize_session=False)

            # Scorer permissions
            session.query(SqlScorerPermission).filter(SqlScorerPermission.user_id == user_id).delete(synchronize_session=False)
            session.query(SqlScorerRegexPermission).filter(SqlScorerRegexPermission.user_id == user_id).delete(synchronize_session=False)

            # Gateway endpoint permissions
            session.query(SqlGatewayEndpointPermission).filter(SqlGatewayEndpointPermission.user_id == user_id).delete(synchronize_session=False)
            session.query(SqlGatewayEndpointRegexPermission).filter(SqlGatewayEndpointRegexPermission.user_id == user_id).delete(synchronize_session=False)

            # Gateway secret permissions
            session.query(SqlGatewaySecretPermission).filter(SqlGatewaySecretPermission.user_id == user_id).delete(synchronize_session=False)
            session.query(SqlGatewaySecretRegexPermission).filter(SqlGatewaySecretRegexPermission.user_id == user_id).delete(synchronize_session=False)

            # Gateway model definition permissions
            session.query(SqlGatewayModelDefinitionPermission).filter(SqlGatewayModelDefinitionPermission.user_id == user_id).delete(synchronize_session=False)
            session.query(SqlGatewayModelDefinitionRegexPermission).filter(SqlGatewayModelDefinitionRegexPermission.user_id == user_id).delete(
                synchronize_session=False
            )

            # Workspace permissions
            session.query(SqlWorkspacePermission).filter(SqlWorkspacePermission.user_id == user_id).delete(synchronize_session=False)
            session.query(SqlWorkspaceRegexPermission).filter(SqlWorkspaceRegexPermission.user_id == user_id).delete(synchronize_session=False)

            # Group memberships
            session.query(SqlUserGroup).filter(SqlUserGroup.user_id == user_id).delete(synchronize_session=False)

            session.delete(user)
            session.flush()

    def authenticate(self, username: str, password: str) -> bool:
        username = normalize_username(username)
        with self._Session() as session:
            try:
                user = get_user(session, username)
                expiration = user.password_expiration
                if expiration is not None:
                    # Normalize into a local, so the comparison does not mark the
                    # persistent user row dirty and flush an UPDATE on every login.
                    if expiration.tzinfo is None:
                        expiration = expiration.replace(tzinfo=timezone.utc)
                    if expiration < datetime.now(timezone.utc):
                        return False
                return check_password_hash(getattr(user, "password_hash"), password)
            except MlflowException:
                return False
