"""Schema operations that a migration can replay after an interrupted run.

MySQL commits every DDL statement on its own, and SQLite (as Alembic drives it) does not run DDL
inside the migration's transaction either. A revision that fails part-way on either backend leaves
the objects it already created in place while the version table still names the previous revision,
so the next start replays the revision from the top and fails on the first object that exists
(#494). On PostgreSQL the whole revision rolls back, and these operations behave exactly like the
plain ``op`` calls they wrap.

``ResumableSchema`` skips an object that already exists, and refuses to continue when it exists in
a weaker shape than this revision creates: a table missing a column, a NOT NULL or a unique
constraint, a column that allows NULL where it should not, or an index with other columns or
uniqueness. What it compares is what a partial run could not have got wrong but a hand repair
could; types and server defaults are not compared. Each skip is logged, so a resumed run is
visible to the operator.

In offline mode (``--sql``) there is no database to inspect, and every statement is emitted.
"""

from typing import Optional, Sequence

import sqlalchemy as sa
from alembic import context, op

from mlflow_oidc_auth.logger import get_logger

logger = get_logger()


class ResumableSchema:
    """Idempotent ``create_table`` / ``add_column`` / ``create_index`` and their reverses."""

    def __init__(self, revision: str) -> None:
        """Bind to the current migration connection.

        Parameters:
            revision: The revision using it, named in the log line for each skipped object.
        """
        self._revision = revision
        self._inspector: Optional[sa.engine.reflection.Inspector] = None if context.is_offline_mode() else sa.inspect(op.get_bind())

    # --- inspection ----------------------------------------------------------------------------

    def _refresh(self) -> None:
        # The inspector caches reflection; every check reads the schema as it is now.
        if self._inspector is not None:
            self._inspector.clear_cache()

    def has_table(self, table: str) -> bool:
        if self._inspector is None:
            return False
        self._refresh()
        return self._inspector.has_table(table)

    def has_column(self, table: str, column: str) -> bool:
        if not self.has_table(table):
            return False
        return column in {c["name"] for c in self._inspector.get_columns(table)}

    def _index(self, table: str, index: str) -> Optional[dict]:
        if not self.has_table(table):
            return None
        return next((i for i in self._inspector.get_indexes(table) if i["name"] == index), None)

    def _skipped(self, what: str) -> None:
        logger.warning("Migration %s: %s already exists, presumably from an interrupted earlier run; not creating it again", self._revision, what)

    # --- operations ----------------------------------------------------------------------------

    def _refuse(self, what: str, problem: str) -> None:
        raise RuntimeError(f"Migration {self._revision}: {what} already exists but {problem}; refusing to record this revision as applied")

    def create_table(self, name: str, *columns) -> None:
        if not self.has_table(name):
            op.create_table(name, *columns)
            return
        # Build the table this revision would create, to compare the existing one against it.
        expected = sa.Table(name, sa.MetaData(), *columns)
        found_columns = {c["name"]: c for c in self._inspector.get_columns(name)}
        missing = [c.name for c in expected.columns if c.name not in found_columns]
        if missing:
            self._refuse(f"table {name}", f"lacks column(s) {missing}")
        loosened = [c.name for c in expected.columns if not c.nullable and found_columns[c.name]["nullable"]]
        if loosened:
            self._refuse(f"table {name}", f"allows NULL in {loosened}")
        # MySQL reports a unique constraint as a unique index, so both are read.
        unique_sets = {frozenset(u["column_names"]) for u in self._inspector.get_unique_constraints(name)}
        unique_sets |= {frozenset(i["column_names"]) for i in self._inspector.get_indexes(name) if i.get("unique")}
        for constraint in expected.constraints:
            if isinstance(constraint, sa.UniqueConstraint) and frozenset(c.name for c in constraint.columns) not in unique_sets:
                self._refuse(f"table {name}", f"lacks the unique constraint on {sorted(c.name for c in constraint.columns)}")
        self._skipped(f"table {name}")

    def add_column(self, table: str, column: sa.Column) -> None:
        if not self.has_column(table, column.name):
            op.add_column(table, column)
            return
        found = next(c for c in self._inspector.get_columns(table) if c["name"] == column.name)
        if not column.nullable and found["nullable"]:
            self._refuse(f"column {table}.{column.name}", "allows NULL")
        self._skipped(f"column {table}.{column.name}")

    def create_index(self, name: str, table: str, columns: Sequence[str], unique: bool = False) -> None:
        found = self._index(table, name)
        if found is None:
            op.create_index(name, table, list(columns), unique=unique)
            return
        if list(found["column_names"]) != list(columns) or bool(found.get("unique")) != unique:
            raise RuntimeError(
                f"Migration {self._revision}: index {name} on {table} already exists as "
                f"{'unique ' if found.get('unique') else ''}{list(found['column_names'])}, not as "
                f"{'unique ' if unique else ''}{list(columns)}; refusing to record this revision as applied"
            )
        self._skipped(f"index {name}")

    def drop_index(self, name: str, table: str) -> None:
        if self._inspector is not None and self._index(table, name) is None:
            return
        op.drop_index(name, table_name=table)

    def drop_column(self, table: str, column: str) -> None:
        if self._inspector is not None and not self.has_column(table, column):
            return
        op.drop_column(table, column)

    def drop_table(self, name: str) -> None:
        # Dropping the table drops its indexes with it. Dropping those first would fail on MySQL
        # for an index a foreign key relies on (error 1553), so callers do not.
        if self._inspector is not None and not self.has_table(name):
            return
        op.drop_table(name)
