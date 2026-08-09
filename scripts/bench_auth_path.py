#!/usr/bin/env python
"""Measure the per-request cost of the authentication path (issue #305).

Every authenticated request passes through ``AuthMiddleware.dispatch``. This script
measures what that costs, in the two units that matter:

* **SQL statements per request** — the round-trip count. Against a remote database this
  dominates; it is also the number the downstream enterprise-identity work is budgeted
  against, so it is reported exactly and must be stable across iterations.
* **Wall time per request** — median and p95 over N iterations, measured at the ASGI
  boundary with ``TestClient`` so middleware overhead is included.

Four scenarios are driven end to end through a real ``AuthMiddleware``:

``unprotected``
    A path matching the middleware's unprotected prefixes. Establishes the floor: the
    auth path is skipped entirely.
``session``
    The browser path — a signed session cookie, as set by the OIDC callback.
``bearer``
    The API path — an RS256 JWT validated against a locally primed JWKS cache. The JWKS
    fetch itself is excluded, matching steady state in production where it is cached for
    ``OIDC_JWKS_CACHE_TTL_SECONDS``.
``basic``
    Username/password, used by MLflow CLI clients and service accounts.

Usage::

    # SQLite (default), full matrix
    python scripts/bench_auth_path.py

    # PostgreSQL
    python scripts/bench_auth_path.py --db-uri postgresql+psycopg2://user@host:5432/db

    # Quick pass while iterating
    python scripts/bench_auth_path.py --users 1 --groups 0 --iterations 50

Output is a Markdown table on stdout; ``--json PATH`` additionally writes the raw
measurements. The recorded baseline lives in ``docs/performance-baseline.md``.
"""

import argparse
import base64
import json
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

# The benchmark configures the plugin through the environment, so every knob has to be
# set before ``mlflow_oidc_auth.config`` is imported (it reads the environment once, at
# import time). Imports of plugin modules therefore happen inside main(), after _configure().
REPO_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_USER_COUNTS = (1, 50, 500)
DEFAULT_GROUP_COUNTS = (0, 20, 200)
SCENARIOS = ("unprotected", "session", "bearer", "basic")

# Statements SQLite and the driver issue that are not application queries.
_IGNORED_PREFIXES = ("PRAGMA", "BEGIN", "COMMIT", "ROLLBACK", "SAVEPOINT", "RELEASE", "SET ", "SHOW ")

BENCH_PASSWORD = "bench-password"  # not a credential: seeded into a throwaway database
PROTECTED_PATH = "/bench/protected"
UNPROTECTED_PATH = "/health/bench"
LOGIN_PATH = "/login/bench"


class QueryCounter:
    """Counts SQL statements issued on an engine while active."""

    def __init__(self) -> None:
        self.statements: List[str] = []

    @property
    def count(self) -> int:
        return len(self.statements)

    def reset(self) -> None:
        self.statements.clear()

    def report(self) -> str:
        lines = [f"{len(self.statements)} statement(s):"]
        for i, stmt in enumerate(self.statements, 1):
            lines.append(f"  {i:2d}. {' '.join(stmt.split())[:160]}")
        return "\n".join(lines)


def _configure(db_uri: str) -> None:
    """Set the environment the plugin reads at import time.

    Deliberately leaves ``OIDC_PROVISION_ON_BEARER_AUTH`` at its default (off) so the
    numbers describe a default deployment. ``OIDC_DISCOVERY_URL`` is set only so
    ``_get_oidc_jwks`` passes its "is it configured" guard — it is never fetched,
    because the JWKS cache is primed directly.
    """
    os.environ["OIDC_USERS_DB_URI"] = db_uri
    os.environ["SECRET_KEY"] = "bench-secret-key-not-a-credential"
    os.environ["OIDC_DISCOVERY_URL"] = "https://bench.invalid/.well-known/openid-configuration"
    os.environ["MLFLOW_ALLOW_FILE_STORE"] = "true"
    os.environ.setdefault("LOG_LEVEL", "ERROR")


def _build_app(store) -> Any:
    """A minimal ASGI app wrapping the real ``AuthMiddleware``.

    Middleware is added in the same order as ``app.py`` (Auth, then Session), which in
    Starlette means Session runs outermost — ``AuthMiddleware`` needs ``request.session``
    to already exist. MLflow's Flask app is not mounted: this measures the auth path,
    not MLflow.
    """
    from fastapi import FastAPI, Request
    from starlette.middleware.sessions import SessionMiddleware

    from mlflow_oidc_auth.config import config
    from mlflow_oidc_auth.middleware import AuthMiddleware

    app = FastAPI()

    @app.get(PROTECTED_PATH)
    async def protected(request: Request):
        return {"username": getattr(request.state, "username", None)}

    @app.get(UNPROTECTED_PATH)
    async def unprotected():
        return {"ok": True}

    @app.get(LOGIN_PATH)
    async def login(request: Request, username: str):
        # Under the "/login" unprotected prefix, so it runs without authentication and
        # mints the same session the OIDC callback would.
        request.session["username"] = username
        return {"ok": True}

    app.add_middleware(AuthMiddleware)
    app.add_middleware(SessionMiddleware, secret_key=config.SECRET_KEY)
    return app


def _seed(store, n_users: int, n_groups: int) -> List[str]:
    """Bulk-insert ``n_users`` users each belonging to ``n_groups`` groups.

    Uses Core inserts rather than the store API: seeding 500 users x 200 groups through
    the ORM takes minutes and none of it is what we are measuring. The password hash is
    computed once and reused, so the basic-auth scenario still verifies a real hash.

    Returns:
        The seeded usernames.
    """
    from sqlalchemy import insert
    from werkzeug.security import generate_password_hash

    from mlflow_oidc_auth.db.models import SqlGroup, SqlUser, SqlUserGroup

    pwhash = generate_password_hash(BENCH_PASSWORD)
    usernames = [f"bench{i}@example.com" for i in range(n_users)]
    group_names = [f"bench-group-{i}" for i in range(n_groups)]

    with store.engine.begin() as conn:
        conn.execute(
            insert(SqlUser),
            [{"username": u, "display_name": u, "password_hash": pwhash, "is_admin": False, "is_service_account": False} for u in usernames],
        )
        if group_names:
            conn.execute(insert(SqlGroup), [{"group_name": g} for g in group_names])
            user_ids = [r[0] for r in conn.exec_driver_sql("SELECT id FROM users ORDER BY id").fetchall()]
            group_ids = [r[0] for r in conn.exec_driver_sql("SELECT id FROM groups ORDER BY id").fetchall()]
            conn.execute(
                insert(SqlUserGroup),
                [{"user_id": uid, "group_id": gid} for uid in user_ids for gid in group_ids],
            )
    return usernames


def _prime_jwks() -> Callable[[str], str]:
    """Prime the JWKS cache with a locally generated key and return a token minter.

    Signature verification is real; only the network fetch is bypassed, which is what a
    warm production process does too.
    """
    from authlib.jose import JsonWebKey, jwt

    import mlflow_oidc_auth.auth as auth_module

    key = JsonWebKey.generate_key("RSA", 2048, is_private=True)
    private = key.as_dict(is_private=True)
    public = key.as_dict(is_private=False)
    kid = public.get("kid") or key.thumbprint()
    public["kid"] = kid
    private["kid"] = kid

    with auth_module._jwks_cache_lock:
        auth_module._jwks_cache[auth_module._JWKS_CACHE_KEY] = {"keys": [public]}

    def mint(username: str) -> str:
        now = int(time.time())
        claims = {"email": username, "name": username, "iat": now, "exp": now + 3600}
        return jwt.encode({"alg": "RS256", "kid": kid}, claims, private).decode("utf-8")

    return mint


def _measure(
    client,
    request: Callable[[], Any],
    counter: QueryCounter,
    iterations: int,
    warmup: int,
) -> Dict[str, Any]:
    """Drive one scenario and return its query count and timing distribution.

    ``queries_per_request`` is reported as an exact integer when every iteration issued
    the same number of statements, and as ``None`` (with ``queries_stable`` False) when
    it varied — a varying count means the scenario is not a usable budget.
    """
    for _ in range(warmup):
        request()

    per_request_queries: List[int] = []
    timings: List[float] = []
    for _ in range(iterations):
        counter.reset()
        start = time.perf_counter()
        response = request()
        elapsed = time.perf_counter() - start
        if response.status_code != 200:
            raise RuntimeError(f"scenario request failed: {response.status_code} {response.text[:200]}")
        per_request_queries.append(counter.count)
        timings.append(elapsed * 1000.0)

    stable = len(set(per_request_queries)) == 1
    timings.sort()
    return {
        "queries_per_request": per_request_queries[0] if stable else None,
        "queries_stable": stable,
        "queries_observed": sorted(set(per_request_queries)),
        "median_ms": round(statistics.median(timings), 4),
        "p95_ms": round(timings[min(len(timings) - 1, int(0.95 * len(timings)))], 4),
        "iterations": iterations,
    }


def _run_matrix(
    db_uri: str,
    db_label: str,
    user_counts: Iterable[int],
    group_counts: Iterable[int],
    scenarios: Iterable[str],
    iterations: int,
    warmup: int,
) -> List[Dict[str, Any]]:
    """Run every (users, groups, scenario) combination against one database."""
    from fastapi.testclient import TestClient
    from sqlalchemy import event

    from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore

    mint_token = _prime_jwks()
    rows: List[Dict[str, Any]] = []

    for n_users in user_counts:
        for n_groups in group_counts:
            store = SqlAlchemyStore()
            store.init_db(db_uri)
            _reset_rows(store)

            usernames = _seed(store, n_users, n_groups)
            # The middleware resolves through the module-level store singleton, so point
            # it at this freshly seeded store rather than constructing a second one.
            _bind_singleton(store)

            counter = QueryCounter()

            def _listener(conn, cursor, statement, parameters, context, executemany):
                if not statement.lstrip().upper().startswith(_IGNORED_PREFIXES):
                    counter.statements.append(statement)

            event.listen(store.engine, "before_cursor_execute", _listener)
            try:
                app = _build_app(store)
                # Measure the last-seeded user: with an index on users.username the row's
                # position should not matter, and measuring the tail makes that visible.
                username = usernames[-1]
                token = mint_token(username)
                basic = base64.b64encode(f"{username}:{BENCH_PASSWORD}".encode()).decode()

                with TestClient(app) as client:
                    client.get(LOGIN_PATH, params={"username": username})
                    requests = {
                        "unprotected": lambda: client.get(UNPROTECTED_PATH),
                        "session": lambda: client.get(PROTECTED_PATH),
                        "bearer": lambda: client.get(PROTECTED_PATH, headers={"Authorization": f"Bearer {token}"}),
                        "basic": lambda: client.get(PROTECTED_PATH, headers={"Authorization": f"Basic {basic}"}),
                    }
                    for scenario in scenarios:
                        result = _measure(client, requests[scenario], counter, iterations, warmup)
                        result.update(db=db_label, users=n_users, groups_per_user=n_groups, scenario=scenario)
                        rows.append(result)
                        print(
                            f"  {db_label:10s} users={n_users:<4d} groups={n_groups:<4d} {scenario:<12s} "
                            f"queries={result['queries_per_request']} median={result['median_ms']}ms p95={result['p95_ms']}ms",
                            file=sys.stderr,
                        )
            finally:
                event.remove(store.engine, "before_cursor_execute", _listener)
                store.engine.dispose()
    return rows


def _bind_singleton(store) -> None:
    """Point the lazy ``store`` singleton at an already-initialised store.

    ``AuthMiddleware`` imports the singleton directly, so the benchmark cannot pass one
    in. This does not construct a second store — it installs the one the benchmark just
    built, keeping the "one store" rule intact.
    """
    import mlflow_oidc_auth.store as store_module

    object.__setattr__(store_module.store, "_instance", store)


def _reset_rows(store) -> None:
    """Empty the user/group tables so each matrix cell starts from a known state.

    Child-before-parent order, so the foreign keys in ``user_groups`` never dangle.
    """
    from sqlalchemy import text

    from mlflow_oidc_auth.db.models import SqlGroup, SqlUser, SqlUserGroup

    with store.engine.begin() as conn:
        for table in (SqlUserGroup.__tablename__, SqlUser.__tablename__, SqlGroup.__tablename__):
            conn.execute(text(f"DELETE FROM {table}"))


def _to_markdown(rows: List[Dict[str, Any]]) -> str:
    """Render the measurements as a Markdown table, one row per matrix cell."""
    header = "| db | users | groups/user | scenario | queries/request | median ms | p95 ms |"
    sep = "|---|---:|---:|---|---:|---:|---:|"
    lines = [header, sep]
    for r in rows:
        queries = r["queries_per_request"] if r["queries_stable"] else f"VARIES {r['queries_observed']}"
        lines.append(f"| {r['db']} | {r['users']} | {r['groups_per_user']} | {r['scenario']} | {queries} | {r['median_ms']} | {r['p95_ms']} |")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db-uri", default=None, help="SQLAlchemy URI. Default: a temporary SQLite database.")
    parser.add_argument("--db-label", default=None, help="Name for this database in the output. Default: the URI's dialect.")
    parser.add_argument("--users", type=int, nargs="+", default=list(DEFAULT_USER_COUNTS))
    parser.add_argument("--groups", type=int, nargs="+", default=list(DEFAULT_GROUP_COUNTS))
    parser.add_argument("--scenarios", nargs="+", default=list(SCENARIOS), choices=list(SCENARIOS))
    parser.add_argument("--iterations", type=int, default=200)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--json", dest="json_path", default=None, help="Also write raw measurements here.")
    args = parser.parse_args(argv)

    tmpdir = None
    db_uri = args.db_uri
    if db_uri is None:
        tmpdir = tempfile.mkdtemp(prefix="bench-auth-")
        db_uri = f"sqlite:///{Path(tmpdir) / 'auth.db'}"
    db_label = args.db_label or db_uri.split(":", 1)[0].split("+", 1)[0]

    _configure(db_uri)
    sys.path.insert(0, str(REPO_ROOT))

    print(f"auth-path benchmark: {db_label} ({args.iterations} iterations/scenario)", file=sys.stderr)
    rows = _run_matrix(
        db_uri=db_uri,
        db_label=db_label,
        user_counts=args.users,
        group_counts=args.groups,
        scenarios=args.scenarios,
        iterations=args.iterations,
        warmup=args.warmup,
    )

    print(_to_markdown(rows))
    if args.json_path:
        Path(args.json_path).write_text(json.dumps(rows, indent=2) + "\n")
        print(f"raw measurements written to {args.json_path}", file=sys.stderr)

    unstable = [r for r in rows if not r["queries_stable"]]
    if unstable:
        print(f"\nWARNING: {len(unstable)} scenario(s) had a varying query count; see 'queries_observed'.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
