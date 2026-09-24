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
    """Delete expired server-side sessions (issue #310), and other expired housekeeping rows.

    Housekeeping, not correctness: an expired session already fails to resolve, so leaving the
    rows in place is safe but unbounded — every login inserts one and nothing else removes them.
    A deployment with a few hundred logins a day accumulates six figures of dead rows in a year.

    Revoked-but-unexpired sessions are kept until their expiry, so that "was this session
    revoked, and when?" stays answerable for the lifetime the session would have had.

    Also sweeps expired SAML replay records (#328) and SCIM activity older than
    ``SCIM_ACTIVITY_RETENTION_DAYS`` (#325; ``0`` keeps it all).

    Run it from cron, or by hand. It is safe to run concurrently with a live server.
    """
    from datetime import datetime, timedelta, timezone

    from mlflow_oidc_auth.config import config
    from mlflow_oidc_auth.db.models import SqlAuthSession, SqlSamlAssertion, SqlScimActivity

    cutoff = datetime.now(timezone.utc).replace(tzinfo=None)
    retention_days = int(getattr(config, "SCIM_ACTIVITY_RETENTION_DAYS", 30) or 0)
    activity_cutoff = cutoff - timedelta(days=retention_days)
    engine = sqlalchemy.create_engine(url)
    try:
        with engine.begin() as conn:
            expired = conn.execute(
                sqlalchemy.select(sqlalchemy.func.count()).select_from(SqlAuthSession).where(SqlAuthSession.expires_at <= cutoff)
            ).scalar_one()
            # SAML replay records (#328) are needed only while their assertion could still
            # validate. Skipped on a database migrated before the table existed.
            inspector = sqlalchemy.inspect(conn)
            has_assertions = inspector.has_table(SqlSamlAssertion.__tablename__)
            expired_assertions = (
                conn.execute(
                    sqlalchemy.select(sqlalchemy.func.count()).select_from(SqlSamlAssertion).where(SqlSamlAssertion.not_on_or_after <= cutoff)
                ).scalar_one()
                if has_assertions
                else 0
            )
            # SCIM activity (#325), likewise skipped before its table exists or when retention is 0.
            sweep_activity = retention_days > 0 and inspector.has_table(SqlScimActivity.__tablename__)
            expired_activity = (
                conn.execute(sqlalchemy.select(sqlalchemy.func.count()).select_from(SqlScimActivity).where(SqlScimActivity.at < activity_cutoff)).scalar_one()
                if sweep_activity
                else 0
            )
            if dry_run:
                click.echo(f"{expired} expired session(s) would be deleted")
                if has_assertions:
                    click.echo(f"{expired_assertions} expired SAML assertion record(s) would be deleted")
                if sweep_activity:
                    click.echo(f"{expired_activity} SCIM activity row(s) older than {retention_days} day(s) would be deleted")
                return
            conn.execute(sqlalchemy.delete(SqlAuthSession).where(SqlAuthSession.expires_at <= cutoff))
            if has_assertions:
                conn.execute(sqlalchemy.delete(SqlSamlAssertion).where(SqlSamlAssertion.not_on_or_after <= cutoff))
            if sweep_activity:
                conn.execute(sqlalchemy.delete(SqlScimActivity).where(SqlScimActivity.at < activity_cutoff))
        click.echo(f"deleted {expired} expired session(s)")
        if has_assertions:
            click.echo(f"deleted {expired_assertions} expired SAML assertion record(s)")
        if sweep_activity:
            click.echo(f"deleted {expired_activity} SCIM activity row(s) older than {retention_days} day(s)")
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
@click.option(
    "--memberships",
    "include_memberships",
    is_flag=True,
    help="Also re-own group memberships (user_groups rows) matching --from-owner / --username.",
)
@click.option(
    "--groups",
    "include_groups",
    is_flag=True,
    help="Re-own groups (groups rows) matching --from-owner / --group instead of user rows.",
)
@click.option("--group", "group_name", default=None, help="With --groups: only this group.")
def reconcile_ownership(
    url: str,
    set_owner: str,
    from_owner: str,
    username: str,
    apply_changes: bool,
    all_rows: bool,
    journal: str,
    include_memberships: bool,
    include_groups: bool = False,
    group_name: str = None,
) -> None:
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

    ``--memberships`` does the same for group memberships (#360), whose owner is recorded per
    ``user_groups`` row. ``--from-owner`` then matches the *membership's* owner, and ``--username``
    the member. Without it a decommissioned source's memberships stay owned by it, and under
    ``enforce`` no other source's sync may remove them.

    ``--groups`` re-owns groups themselves (``groups.managed_by``) and leaves user rows alone. It is
    how an operator lets a directory manage a group that existed before it, under ``enforce``:
    ``--groups --group data-eng --set-owner scim``.
    """
    import json as _json
    import re as _re
    from datetime import datetime, timezone

    from mlflow_oidc_auth.db.models import SqlGroup, SqlUser, SqlUserGroup

    # An owner string no source will ever present is worse than a rejected one: under 'enforce'
    # every writer then conflicts with it forever, and the operator was usually in the middle of
    # repairing a lockout when they typed it.
    from mlflow_oidc_auth.ownership import OWNER_PATTERN

    if not _re.fullmatch(OWNER_PATTERN, set_owner or ""):
        raise click.ClickException(
            f"--set-owner {set_owner!r} is not an owner any source presents. Expected 'manual', 'scim', 'oidc:<provider-id>' or 'saml:<provider-id>'."
        )

    # Every filter must constrain the table it is given for. A filter that silently does not apply
    # turns a targeted repair into a rewrite of the whole table: `--groups --username alice` used
    # to re-own every group.
    if include_groups:
        if include_memberships:
            raise click.ClickException("--groups and --memberships re-own different tables; run them separately.")
        if username:
            raise click.ClickException("--username does not apply to --groups. Narrow it with --group or --from-owner.")
        if not from_owner and not group_name and not all_rows:
            raise click.ClickException("refusing to re-own every group without --all. Narrow it with --group or --from-owner, or pass --all deliberately.")
    else:
        if group_name:
            raise click.ClickException("--group applies only with --groups. Narrow user rows and memberships with --username or --from-owner.")
        if not from_owner and not username and not all_rows:
            raise click.ClickException(
                "refusing to re-own every user row without --all. Narrow it with --from-owner or --username, or pass --all deliberately."
            )

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
            rows = [] if include_groups else [row for row in conn.execute(query).fetchall() if (row.managed_by or "manual") != set_owner]

            groups = []
            if include_groups:
                group_query = sqlalchemy.select(SqlGroup.id, SqlGroup.group_name, SqlGroup.managed_by).order_by(SqlGroup.id)
                if from_owner:
                    group_query = group_query.where(SqlGroup.managed_by == from_owner)
                if group_name:
                    group_query = group_query.where(SqlGroup.group_name == group_name)
                groups = [row for row in conn.execute(group_query).fetchall() if (row.managed_by or "manual") != set_owner]

            memberships = []
            if include_memberships:
                membership_query = (
                    sqlalchemy.select(SqlUserGroup.id, SqlUser.username, SqlGroup.group_name, SqlUserGroup.managed_by)
                    .join(SqlUser, SqlUser.id == SqlUserGroup.user_id)
                    .join(SqlGroup, SqlGroup.id == SqlUserGroup.group_id)
                    .order_by(SqlUserGroup.id)
                )
                if from_owner:
                    membership_query = membership_query.where(SqlUserGroup.managed_by == from_owner)
                if username:
                    membership_query = membership_query.where(SqlUser.username == username.strip().lower())
                memberships = [row for row in conn.execute(membership_query).fetchall() if (row.managed_by or "manual") != set_owner]

            if not rows and not memberships and not groups:
                click.echo("no rows to change")
                return

            for row in groups:
                click.echo(f"group {row.group_name}: {row.managed_by or 'manual'} -> {set_owner}")

            for row in rows:
                click.echo(f"{row.username}: {row.managed_by or 'manual'} -> {set_owner}")
            for row in memberships:
                click.echo(f"{row.username} in {row.group_name}: {row.managed_by or 'manual'} -> {set_owner}")

            if not apply_changes:
                click.echo(f"\n{len(rows) + len(memberships) + len(groups)} row(s) would change. Re-run with --apply to write them.")
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
                            "memberships": [{"username": row.username, "group": row.group_name, "managed_by": row.managed_by} for row in memberships],
                            "groups": [{"group": row.group_name, "managed_by": row.managed_by} for row in groups],
                        },
                        handle,
                        indent=2,
                    )
                click.echo(f"prior ownership recorded in {journal}")

            for row in rows:
                conn.execute(sqlalchemy.update(SqlUser).where(SqlUser.username == row.username).values(managed_by=set_owner))
            for row in memberships:
                conn.execute(sqlalchemy.update(SqlUserGroup).where(SqlUserGroup.id == row.id).values(managed_by=set_owner))
            for row in groups:
                conn.execute(sqlalchemy.update(SqlGroup).where(SqlGroup.id == row.id).values(managed_by=set_owner))

        if rows:
            emit_ownership_audit("user.ownership_reconciled", set_owner, [row.username for row in rows])
        if memberships:
            emit_ownership_audit("membership.ownership_reconciled", set_owner, [f"{row.username}:{row.group_name}" for row in memberships])
        if groups:
            emit_ownership_audit("group.ownership_reconciled", set_owner, [row.group_name for row in groups], resource_type="group")
        click.echo(f"\nchanged {len(rows) + len(memberships) + len(groups)} row(s)")
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

    from mlflow_oidc_auth.db.models import SqlGroup, SqlUser, SqlUserGroup

    with open(journal, "r", encoding="utf-8") as handle:
        recorded = _json.load(handle)

    previous = recorded.get("previous") or []
    # Membership ownership (#360), present only in journals written with --memberships.
    memberships = recorded.get("memberships") or []
    groups = recorded.get("groups") or []
    if not previous and not memberships and not groups:
        click.echo("journal records no changes")
        return

    engine = sqlalchemy.create_engine(url)
    try:
        for entry in previous:
            click.echo(f"{entry['username']}: -> {entry['managed_by'] or 'manual'}")
        for entry in memberships:
            click.echo(f"{entry['username']} in {entry['group']}: -> {entry['managed_by'] or 'manual'}")
        for entry in groups:
            click.echo(f"group {entry['group']}: -> {entry['managed_by'] or 'manual'}")

        if not apply_changes:
            click.echo(f"\n{len(previous) + len(memberships) + len(groups)} row(s) would be restored. Re-run with --apply to write them.")
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
            for entry in memberships:
                # Addressed by (member, group) rather than row id: a membership removed and
                # granted again since is a different decision, and is left alone like any other.
                user_id = sqlalchemy.select(SqlUser.id).where(SqlUser.username == entry["username"]).scalar_subquery()
                group_id = sqlalchemy.select(SqlGroup.id).where(SqlGroup.group_name == entry["group"]).scalar_subquery()
                result = conn.execute(
                    sqlalchemy.update(SqlUserGroup)
                    .where(SqlUserGroup.user_id == user_id, SqlUserGroup.group_id == group_id, SqlUserGroup.managed_by == recorded.get("set_owner"))
                    .values(managed_by=entry["managed_by"] or "manual")
                )
                if result.rowcount:
                    restored += int(result.rowcount)
                else:
                    skipped.append(f"{entry['username']} in {entry['group']}")
            for entry in groups:
                result = conn.execute(
                    sqlalchemy.update(SqlGroup)
                    .where(SqlGroup.group_name == entry["group"], SqlGroup.managed_by == recorded.get("set_owner"))
                    .values(managed_by=entry["managed_by"] or "manual")
                )
                if result.rowcount:
                    restored += int(result.rowcount)
                else:
                    skipped.append(f"group {entry['group']}")

        if previous:
            emit_ownership_audit("user.ownership_restored", recorded.get("set_owner"), [entry["username"] for entry in previous])
        if memberships:
            emit_ownership_audit("membership.ownership_restored", recorded.get("set_owner"), [f"{e['username']}:{e['group']}" for e in memberships])
        if groups:
            emit_ownership_audit("group.ownership_restored", recorded.get("set_owner"), [e["group"] for e in groups], resource_type="group")
        click.echo(f"\nrestored {restored} row(s)")
        if skipped:
            click.echo(f"left alone (changed since the journal was written): {', '.join(skipped)}")
    finally:
        engine.dispose()


def emit_ownership_audit(event: str, owner, names, resource_type: str = "user") -> None:
    """Record a bulk ownership change. Out of band by nature, so it belongs in the audit log.

    ``resource_type`` names what was re-owned: ``user`` (user rows and ``user:group``
    memberships, which belong to a user) or ``group``.
    """
    from mlflow_oidc_auth.audit import emit_audit_event

    emit_audit_event(
        event,
        actor="cli",
        resource_type=resource_type,
        resource_id=",".join(names[:20]) + ("..." if len(names) > 20 else ""),
        detail={"owner": owner, "count": len(names)},
    )
