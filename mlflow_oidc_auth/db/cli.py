import click
import sqlalchemy

from mlflow_oidc_auth.db import utils


@click.group(name="db")
def commands():
    pass


@commands.command()
@click.option("--url", required=True)
@click.option("--revision", default="head")
def upgrade(url: str, revision: str) -> None:
    engine = sqlalchemy.create_engine(url)
    utils.migrate(engine, revision)
    engine.dispose()


@commands.command(name="assign-owners")
@click.option("--url", required=True, help="Database URL (same as OIDC_USERS_DB_URI)")
def assign_owners(url: str) -> None:
    """Assign OWNER permission to experiments that only have MANAGE holders.

    For each experiment that has at least one MANAGE permission but no OWNER,
    the lexicographically first MANAGE holder is promoted to OWNER.
    Run this once after upgrading to add the OWNER permission concept.
    """
    from mlflow_oidc_auth.config import config as app_config

    app_config.OIDC_USERS_DB_URI = url

    from mlflow_oidc_auth.store import store
    from mlflow_oidc_auth.permissions import MANAGE, OWNER
    from mlflow_oidc_auth.db.models import SqlExperimentPermission, SqlUser

    engine = sqlalchemy.create_engine(url)
    from mlflow.store.db.utils import _get_managed_session_maker, create_sqlalchemy_engine_with_retry
    from sqlalchemy.orm import sessionmaker
    from mlflow.utils.uri import extract_db_type_from_uri
    from mlflow.store.db.utils import _get_managed_session_maker

    db_type = extract_db_type_from_uri(url)
    eng = create_sqlalchemy_engine_with_retry(url)
    Session = sessionmaker(bind=eng)
    ManagedSession = _get_managed_session_maker(Session, db_type)

    promoted = 0
    skipped = 0

    with ManagedSession() as session:
        # Find all distinct experiment_ids in the permissions table
        experiment_ids = [
            row[0]
            for row in session.query(SqlExperimentPermission.experiment_id).distinct().all()
        ]

    for exp_id in experiment_ids:
        with ManagedSession() as session:
            perms = (
                session.query(SqlExperimentPermission)
                .join(SqlUser, SqlExperimentPermission.user_id == SqlUser.id)
                .filter(SqlExperimentPermission.experiment_id == exp_id)
                .all()
            )
            has_owner = any(p.permission == OWNER.name for p in perms)
            if has_owner:
                skipped += 1
                continue

            manage_perms = sorted(
                [(p, session.query(SqlUser).filter(SqlUser.id == p.user_id).one().username) for p in perms if p.permission == MANAGE.name],
                key=lambda x: x[1],
            )
            if not manage_perms:
                skipped += 1
                continue

            first_perm, first_username = manage_perms[0]
            first_perm.permission = OWNER.name
            session.flush()
            click.echo(f"Experiment {exp_id}: promoted '{first_username}' to OWNER")
            promoted += 1

    click.echo(f"\nDone. Promoted: {promoted}, Skipped (already had owner or no MANAGE): {skipped}")
    eng.dispose()
