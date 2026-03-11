from datetime import datetime, timezone
from typing import Callable, List, Optional

from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.db.models.quota import SqlUserQuota
from mlflow_oidc_auth.db.models.user import SqlUser
from mlflow_oidc_auth.repository.utils import get_user


class QuotaRepository:
    def __init__(self, session_maker: Callable[[], Session]) -> None:
        self._Session = session_maker

    def _get_or_none(self, session: Session, username: str) -> Optional[SqlUserQuota]:
        user = session.query(SqlUser).filter(SqlUser.username == username).one_or_none()
        if user is None:
            return None
        return session.query(SqlUserQuota).filter(SqlUserQuota.user_id == user.id).one_or_none()

    def get_quota(self, username: str) -> Optional[SqlUserQuota]:
        with self._Session() as session:
            return self._get_or_none(session, username)

    def get_quota_by_user_id(self, user_id: int) -> Optional[SqlUserQuota]:
        with self._Session() as session:
            return session.query(SqlUserQuota).filter(SqlUserQuota.user_id == user_id).one_or_none()

    def list_all_quotas(self) -> List[SqlUserQuota]:
        with self._Session() as session:
            return session.query(SqlUserQuota).all()

    def set_quota(self, username: str, quota_bytes: Optional[int], soft_cap_fraction: Optional[float] = None) -> SqlUserQuota:
        with self._Session() as session:
            user = get_user(session, username)
            quota = session.query(SqlUserQuota).filter(SqlUserQuota.user_id == user.id).one_or_none()
            if quota is None:
                quota = SqlUserQuota(
                    user_id=user.id,
                    quota_bytes=quota_bytes,
                    used_bytes=0,
                    soft_cap_fraction=soft_cap_fraction if soft_cap_fraction is not None else 0.9,
                    hard_blocked=False,
                )
                session.add(quota)
            else:
                quota.quota_bytes = quota_bytes
                if soft_cap_fraction is not None:
                    quota.soft_cap_fraction = soft_cap_fraction
            session.flush()
            session.expunge(quota)
            return quota

    def update_email(self, username: str, email: Optional[str]) -> None:
        with self._Session() as session:
            user = session.query(SqlUser).filter(SqlUser.username == username).one_or_none()
            if user is None:
                return
            quota = session.query(SqlUserQuota).filter(SqlUserQuota.user_id == user.id).one_or_none()
            if quota is None:
                # Create a quota row so the email is ready when an admin assigns
                # a limit later.  Seed quota_bytes from the global default so
                # enforcement behaves consistently whether or not an explicit row
                # existed before.
                quota = SqlUserQuota(
                    user_id=user.id,
                    quota_bytes=config.QUOTA_DEFAULT_BYTES,
                    used_bytes=0,
                    soft_cap_fraction=config.QUOTA_SOFT_CAP_FRACTION,
                    hard_blocked=False,
                    email=email,
                )
                session.add(quota)
            else:
                quota.email = email
            session.flush()

    def delete_quota(self, username: str) -> None:
        with self._Session() as session:
            user = session.query(SqlUser).filter(SqlUser.username == username).one_or_none()
            if user is None:
                return
            session.query(SqlUserQuota).filter(SqlUserQuota.user_id == user.id).delete(synchronize_session=False)
            session.flush()

    def update_used_bytes(self, username: str, used_bytes: int) -> None:
        with self._Session() as session:
            user = session.query(SqlUser).filter(SqlUser.username == username).one_or_none()
            if user is None:
                return
            quota = session.query(SqlUserQuota).filter(SqlUserQuota.user_id == user.id).one_or_none()
            if quota is None:
                return
            quota.used_bytes = used_bytes
            quota.last_reconciled_at = datetime.now(timezone.utc)
            session.flush()

    def increment_used_bytes(self, username: str, delta: int) -> None:
        with self._Session() as session:
            user = session.query(SqlUser).filter(SqlUser.username == username).one_or_none()
            if user is None:
                return
            quota = session.query(SqlUserQuota).filter(SqlUserQuota.user_id == user.id).one_or_none()
            if quota is None:
                return
            quota.used_bytes = max(0, quota.used_bytes + delta)
            session.flush()

    def set_hard_blocked(self, username: str, blocked: bool) -> None:
        with self._Session() as session:
            user = session.query(SqlUser).filter(SqlUser.username == username).one_or_none()
            if user is None:
                return
            quota = session.query(SqlUserQuota).filter(SqlUserQuota.user_id == user.id).one_or_none()
            if quota is None:
                return
            quota.hard_blocked = blocked
            session.flush()

    def set_soft_notified_at(self, username: str, value: Optional[datetime]) -> None:
        with self._Session() as session:
            user = session.query(SqlUser).filter(SqlUser.username == username).one_or_none()
            if user is None:
                return
            quota = session.query(SqlUserQuota).filter(SqlUserQuota.user_id == user.id).one_or_none()
            if quota is None:
                return
            quota.soft_notified_at = value
            session.flush()
