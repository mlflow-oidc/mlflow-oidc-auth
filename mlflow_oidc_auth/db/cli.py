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


@commands.command(name="restore-admin")
@click.option("--url", required=True, help="Database URL, e.g. sqlite:///auth.db")
@click.option("--username", required=True, help="User to restore administrator access to.")
def restore_admin(url: str, username: str) -> None:
    """Break-glass recovery: make a user an active administrator again.

    The last-active-admin invariant in the store makes a full lockout hard to reach, but not
    impossible — a database restored from a backup, a directory sync that ran before the guard
    existed, or a deliberate override can all leave a deployment with no administrator who can
    log in. At that point nothing can be fixed over HTTP: every route that could grant admin
    requires an admin.

    So this deliberately bypasses the application entirely. It talks to the database directly,
    performs no authentication, and is only as safe as access to the database URL — which is
    precisely the out-of-band authority the situation calls for.

    It sets ``is_admin=true``, ``active=true`` and ``managed_by='manual'``. Resetting
    ``managed_by`` matters as much as the other two: leaving a row owned by ``scim`` or
    ``oidc:<provider>`` invites the next sync to undo the repair, and the #319 write guard to
    refuse an admin's later edits to it.

    Prints what it changed, and emits an audit event, because an out-of-band privilege grant is
    exactly the kind of thing an operator needs to find in the log afterwards.
    """
    from mlflow_oidc_auth.audit import emit_audit_event
    from mlflow_oidc_auth.db.models import SqlUser

    engine = sqlalchemy.create_engine(url)
    try:
        with engine.begin() as conn:
            row = conn.execute(
                sqlalchemy.select(SqlUser.id, SqlUser.is_admin, SqlUser.active, SqlUser.managed_by).where(SqlUser.username == username)
            ).fetchone()
            if row is None:
                raise click.ClickException(f"user '{username}' does not exist in this database")

            conn.execute(sqlalchemy.update(SqlUser).where(SqlUser.username == username).values(is_admin=True, active=True, managed_by="manual"))

        emit_audit_event(
            "user.break_glass_admin_restore",
            actor="cli",
            resource_type="user",
            resource_id=username,
            detail={
                "previous_is_admin": bool(row.is_admin),
                "previous_active": bool(row.active),
                "previous_managed_by": row.managed_by,
            },
        )
        click.echo(
            f"restored '{username}': is_admin {bool(row.is_admin)} -> True, active {bool(row.active)} -> True, managed_by {row.managed_by!r} -> 'manual'"
        )
    finally:
        engine.dispose()
