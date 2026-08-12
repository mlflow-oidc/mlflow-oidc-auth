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


@commands.command(name="prune-sessions")
@click.option("--url", required=True, help="Database URL, e.g. sqlite:///auth.db")
@click.option("--dry-run", is_flag=True, help="Report how many rows would be deleted, and delete nothing.")
def prune_sessions(url: str, dry_run: bool) -> None:
    """Delete expired server-side sessions (issue #310).

    Housekeeping, not correctness: an expired session already fails to resolve, so leaving the
    rows in place is safe but unbounded — every login inserts one and nothing else removes them.
    A deployment with a few hundred logins a day accumulates six figures of dead rows in a year.

    Revoked-but-unexpired sessions are kept until their expiry, so that "was this session
    revoked, and when?" stays answerable for the lifetime the session would have had.

    Run it from cron, or by hand. It is safe to run concurrently with a live server.
    """
    from datetime import datetime, timezone

    from mlflow_oidc_auth.db.models import SqlAuthSession

    cutoff = datetime.now(timezone.utc).replace(tzinfo=None)
    engine = sqlalchemy.create_engine(url)
    try:
        with engine.begin() as conn:
            expired = conn.execute(
                sqlalchemy.select(sqlalchemy.func.count()).select_from(SqlAuthSession).where(SqlAuthSession.expires_at <= cutoff)
            ).scalar_one()
            if dry_run:
                click.echo(f"{expired} expired session(s) would be deleted")
                return
            conn.execute(sqlalchemy.delete(SqlAuthSession).where(SqlAuthSession.expires_at <= cutoff))
        click.echo(f"deleted {expired} expired session(s)")
    finally:
        engine.dispose()


@commands.command(name="reconcile-ownership")
@click.option("--url", required=True, help="Database URL, e.g. sqlite:///auth.db")
@click.option("--set-owner", required=True, help="The managed_by value to write, e.g. 'manual' or 'scim'.")
@click.option("--from-owner", default=None, help="Only rows currently owned by this. Omit to match any owner.")
@click.option("--username", default=None, help="Only this user. Omit for every matching row.")
@click.option("--apply", "apply_changes", is_flag=True, help="Actually write. Without it, nothing is changed.")
@click.option("--all", "all_rows", is_flag=True, help="Required to match every row: without a filter this rewrites the whole user table.")
@click.option("--journal", default=None, help="Where to record prior ownership, so a mistaken run can be rolled back.")
def reconcile_ownership(url: str, set_owner: str, from_owner: str, username: str, apply_changes: bool, all_rows: bool, journal: str) -> None:
    """Change which source owns user rows (issue #319).

    **Dry run unless ``--apply`` is given**, and it never runs implicitly — not at startup, not
    on a configuration change, not as a side effect of anything. Grafana shipped a silent runtime
    branch that reset existing users ([grafana#73752](https://github.com/grafana/grafana/issues/73752));
    the lesson is that ownership changes are an operator action with a diff they read first.

    The diff a dry run prints is the diff an apply performs: both come from the same query, so
    what you approve is what runs.

    With ``--journal`` the prior ownership of every changed row is written to a JSON file before
    anything is modified, and ``restore-ownership`` puts it back.

    This is also the repair path when a source is turned off: point ``--from-owner`` at it and
    ``--set-owner`` at ``manual``, and the rows it used to own become editable again.
    """
    import json as _json
    import re as _re
    from datetime import datetime, timezone

    from mlflow_oidc_auth.db.models import SqlUser

    # An owner string no source will ever present is worse than a rejected one: under 'enforce'
    # every writer then conflicts with it forever, and the operator was usually in the middle of
    # repairing a lockout when they typed it.
    if not _re.fullmatch(r"manual|scim|oidc:[A-Za-z0-9._-]+", set_owner or ""):
        raise click.ClickException(f"--set-owner {set_owner!r} is not an owner any source presents. Expected 'manual', 'scim', or 'oidc:<provider-id>'.")

    if not from_owner and not username and not all_rows:
        raise click.ClickException("refusing to re-own every user row without --all. Narrow it with --from-owner or --username, or pass --all deliberately.")

    engine = sqlalchemy.create_engine(url)
    try:
        with engine.begin() as conn:
            query = sqlalchemy.select(SqlUser.username, SqlUser.managed_by)
            if from_owner:
                query = query.where(SqlUser.managed_by == from_owner)
            if username:
                # Stored normalized, so a targeted repair typed in display capitalisation would
                # otherwise match nothing and report "ownership is already fine".
                query = query.where(SqlUser.username == username.strip().lower())
            rows = [row for row in conn.execute(query).fetchall() if (row.managed_by or "manual") != set_owner]

            if not rows:
                click.echo("no rows to change")
                return

            for row in rows:
                click.echo(f"{row.username}: {row.managed_by or 'manual'} -> {set_owner}")

            if not apply_changes:
                click.echo(f"\n{len(rows)} row(s) would change. Re-run with --apply to write them.")
                return

            if journal:
                # 'x' rather than 'w': two runs pointed at one path would otherwise leave only
                # the second recoverable, and the first run's prior ownership gone. Reported as
                # an operator error, because this command is read during a repair.
                try:
                    handle = open(journal, "x", encoding="utf-8")
                except FileExistsError:
                    raise click.ClickException(f"{journal} already exists, and overwriting it would discard the prior run's rollback. Choose another path.")
                with handle:
                    _json.dump(
                        {
                            "recorded_at": datetime.now(timezone.utc).isoformat(),
                            "set_owner": set_owner,
                            "previous": [{"username": row.username, "managed_by": row.managed_by} for row in rows],
                        },
                        handle,
                        indent=2,
                    )
                click.echo(f"prior ownership recorded in {journal}")

            for row in rows:
                conn.execute(sqlalchemy.update(SqlUser).where(SqlUser.username == row.username).values(managed_by=set_owner))

        emit_ownership_audit("user.ownership_reconciled", set_owner, [row.username for row in rows])
        click.echo(f"\nchanged {len(rows)} row(s)")
    finally:
        engine.dispose()


@commands.command(name="restore-ownership")
@click.option("--url", required=True, help="Database URL, e.g. sqlite:///auth.db")
@click.option("--journal", required=True, help="A journal written by reconcile-ownership --apply --journal.")
@click.option("--apply", "apply_changes", is_flag=True, help="Actually write. Without it, nothing is changed.")
def restore_ownership(url: str, journal: str, apply_changes: bool) -> None:
    """Put ownership back the way a journalled reconciliation found it (issue #319).

    Reversibility is the point: a reconciliation that turns out to have been wrong is otherwise
    a hand-written UPDATE against production, from someone who has just learned they should not
    be trusted with hand-written UPDATEs against production.
    """
    import json as _json

    from mlflow_oidc_auth.db.models import SqlUser

    with open(journal, "r", encoding="utf-8") as handle:
        recorded = _json.load(handle)

    previous = recorded.get("previous") or []
    if not previous:
        click.echo("journal records no changes")
        return

    engine = sqlalchemy.create_engine(url)
    try:
        for entry in previous:
            click.echo(f"{entry['username']}: -> {entry['managed_by'] or 'manual'}")

        if not apply_changes:
            click.echo(f"\n{len(previous)} row(s) would be restored. Re-run with --apply to write them.")
            return

        restored = 0
        skipped = []
        with engine.begin() as conn:
            for entry in previous:
                # Only rows that still hold what the reconcile wrote. A row re-owned since then
                # is somebody's newer decision, and silently reverting it would be a second,
                # unjournalled loss.
                result = conn.execute(
                    sqlalchemy.update(SqlUser)
                    .where(SqlUser.username == entry["username"], SqlUser.managed_by == recorded.get("set_owner"))
                    .values(managed_by=entry["managed_by"])
                )
                if result.rowcount:
                    restored += int(result.rowcount)
                else:
                    skipped.append(entry["username"])

        emit_ownership_audit("user.ownership_restored", recorded.get("set_owner"), [entry["username"] for entry in previous])
        click.echo(f"\nrestored {restored} row(s)")
        if skipped:
            click.echo(f"left alone (changed since the journal was written): {', '.join(skipped)}")
    finally:
        engine.dispose()


def emit_ownership_audit(event: str, owner, usernames) -> None:
    """Record a bulk ownership change. Out of band by nature, so it belongs in the audit log."""
    from mlflow_oidc_auth.audit import emit_audit_event

    emit_audit_event(
        event,
        actor="cli",
        resource_type="user",
        resource_id=",".join(usernames[:20]) + ("..." if len(usernames) > 20 else ""),
        detail={"owner": owner, "count": len(usernames)},
    )
