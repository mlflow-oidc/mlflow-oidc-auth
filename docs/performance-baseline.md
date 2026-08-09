# Auth-path performance baseline

Every request that is not on an unprotected prefix passes through `AuthMiddleware.dispatch`.
Whatever that costs is paid by every API call and every UI navigation, so it is the budget the
rest of the authentication work is held against.

This page records the measured baseline (issue #305) and states the budget derived from it.

> **The budget: no change may raise the per-request statement counts in the table below.**
> A change that needs more per-request data must fit it into the existing statements — widen the
> `load_only` in `UserRepository.get_profile` — or cache it. It may not add a query.
> The budget is enforced by `mlflow_oidc_auth/tests/perf/test_auth_path_baseline.py`, which
> asserts the counts exactly: a regression *and* a silent improvement both fail, so the number
> has to change in a diff, deliberately.

## Running the benchmark

```bash
# SQLite (default), full matrix
python scripts/bench_auth_path.py

# PostgreSQL
python scripts/bench_auth_path.py --db-uri postgresql+psycopg2://user@host:5432/db

# Just the statement counts, as a test
pytest mlflow_oidc_auth/tests/perf/test_auth_path_baseline.py
```

`--users`, `--groups`, `--scenarios`, `--iterations` and `--json` narrow or redirect a run;
`--help` lists them. The script exits non-zero if any scenario's statement count varies between
iterations, since a varying count is not a usable budget.

## What is measured

Four scenarios are driven end to end through a real `AuthMiddleware`, in a minimal ASGI app with
the same middleware order as `app.py`. MLflow's Flask application is not mounted — this is the
cost of authentication, not of MLflow.

| Scenario | What it represents |
|---|---|
| `unprotected` | A path on an unprotected prefix (`/health`, `/oidc/ui`, `/static-files`, …). The floor. |
| `session` | The browser path — a signed session cookie, as set by the OIDC callback. |
| `bearer` | The API path — an RS256 JWT validated against a warm JWKS cache. |
| `basic` | Username/password, as used by MLflow CLI clients and service accounts. |

Two units are reported:

- **SQL statements per request** — the round-trip count. Against a remote database this dominates,
  and it is the number the budget is written in. It is dialect-independent: the count comes from
  the SQLAlchemy loader strategy, not from the driver, which is why SQLite and PostgreSQL agree
  below.
- **Wall time** — median and p95 over 200 iterations, measured at the ASGI boundary. This is
  hardware- and dialect-specific and is recorded for orientation, not as a contract. Both
  databases here are local, so the numbers understate a production round trip.

Bearer measurements exclude the JWKS network fetch, matching steady state in production where the
key set is cached for `OIDC_JWKS_CACHE_TTL_SECONDS`. Signature verification is real.

## Baseline

Measured 2026-08-09 on `d1d44ef`, Apple M-series / macOS, Python 3.14, SQLAlchemy 2.0.46,
MLflow 3.14.0, PostgreSQL 18.3 (local), 200 iterations per scenario.

### Statements per request — the budget

Identical in all 72 cells (2 databases x {1, 50, 500} users x {0, 20, 200} groups per user):

| Scenario | Statements per request | Where they go |
|---|---:|---|
| `unprotected` | **0** | `_is_unprotected_route` returns before any store access |
| `session` | **2** | `_get_user_admin_status` -> `get_profile`: one `load_only` select on `users`, one `selectinload` on `groups` |
| `bearer` | **2** | same; token validation itself touches no database |
| `basic` | **3** | one select in `authenticate_user` to load the password hash, then the 2 above |

Denial paths, asserted in `test_auth_path_baseline.py`:

| Denied request | Statements |
|---|---:|
| No credentials | **0** |
| Invalid/forged bearer token | **0** |
| Basic auth, wrong password | **1** |
| Basic auth, unknown user | **1** |

### Wall time

Median / p95 milliseconds per request at the ASGI boundary. Both databases are local, so
these understate a production round trip; they are recorded for orientation, not as a contract.

> The `basic` column is the **T0** measurement, taken before #336 changed how token secrets are
> hashed. It now costs ~2.8 ms rather than ~50 ms for any secret written after that change; see
> the findings below. The other three columns are unaffected.

| db | users | groups/user | unprotected | session | bearer | basic |
|---|---:|---:|---|---|---|---|
| sqlite | 1 | 0 | 0.41 / 0.48 | 1.09 / 1.28 | 1.28 / 1.74 | 48.91 / 51.23 |
| sqlite | 1 | 20 | 0.45 / 0.57 | 1.32 / 1.82 | 1.43 / 1.83 | 51.10 / 53.18 |
| sqlite | 1 | 200 | 0.49 / 0.59 | 2.41 / 2.85 | 2.63 / 2.95 | 52.59 / 54.52 |
| sqlite | 50 | 0 | 0.50 / 0.65 | 1.51 / 1.84 | 1.64 / 1.86 | 52.14 / 54.07 |
| sqlite | 50 | 20 | 0.49 / 0.58 | 1.56 / 1.81 | 1.64 / 1.89 | 51.19 / 54.30 |
| sqlite | 50 | 200 | 0.43 / 0.58 | 2.03 / 2.42 | 2.15 / 3.07 | 51.65 / 53.76 |
| sqlite | 500 | 0 | 0.40 / 0.43 | 1.30 / 1.74 | 1.16 / 1.36 | 50.32 / 52.59 |
| sqlite | 500 | 20 | 0.44 / 0.52 | 1.27 / 1.89 | 1.34 / 1.67 | 50.85 / 55.93 |
| sqlite | 500 | 200 | 0.48 / 0.65 | 1.95 / 2.61 | 2.08 / 2.78 | 51.75 / 56.25 |
| postgres | 1 | 0 | 0.43 / 0.47 | 1.48 / 2.05 | 1.57 / 2.22 | 53.44 / 55.41 |
| postgres | 1 | 20 | 0.52 / 0.64 | 1.90 / 2.46 | 2.36 / 2.88 | 53.99 / 56.69 |
| postgres | 1 | 200 | 0.57 / 0.71 | 3.14 / 4.21 | 3.43 / 4.57 | 55.15 / 67.37 |
| postgres | 50 | 0 | 0.51 / 0.62 | 2.23 / 3.63 | 2.44 / 2.89 | 52.37 / 55.48 |
| postgres | 50 | 20 | 0.42 / 0.50 | 1.57 / 1.87 | 1.74 / 1.95 | 51.88 / 53.74 |
| postgres | 50 | 200 | 0.43 / 0.54 | 2.38 / 2.98 | 2.58 / 4.03 | 52.34 / 54.31 |
| postgres | 500 | 0 | 0.42 / 0.50 | 1.39 / 1.55 | 1.47 / 1.67 | 51.10 / 53.13 |
| postgres | 500 | 20 | 0.42 / 0.49 | 1.51 / 1.88 | 1.73 / 2.98 | 51.49 / 54.13 |
| postgres | 500 | 200 | 0.44 / 0.54 | 2.75 / 4.28 | 2.93 / 3.89 | 54.89 / 57.68 |

## Findings

**The 2-query claim is confirmed, with one correction to its scope.**

Issue #305 stated that `_get_user_admin_status` "runs on every authenticated request and issues
2 uncached queries via `get_profile`". Measured:

- **2 queries: confirmed.** `UserRepository.get_profile` emits exactly two statements — a
  `load_only` select on `users` and a `selectinload` on `groups`. This holds on SQLite and
  PostgreSQL alike, and at every point in the matrix.
- **Uncached: confirmed.** Two consecutive `get_user_profile` calls cost four statements. Nothing
  on this path consults `PERMISSION_CACHE_TTL_SECONDS` or the `mlflow_oidc_auth/cache/` backend,
  both of which exist and are used elsewhere.
- **"On every request": too strong.** Requests on an unprotected prefix — `/health`, `/login`,
  `/callback`, `/oidc/static`, `/oidc/ui`, `/metrics`, `/docs`, `/redoc`, `/openapi.json` and
  `/static-files` — return from `dispatch` before any store access, at **0 queries**. Since
  `/static-files` serves MLflow's entire React bundle, a real browser session issues many more
  0-query requests than 2-query ones. The claim is correct for every *authenticated* request;
  it is not correct for every request.
- **Basic auth costs 3, not 2.** `store.authenticate_user` adds a select to load the password
  hash before the admin check runs. Any downstream work that assumes a flat 2 has to account
  for this path.

**The count is constant in both dimensions of the matrix.** Statement count does not move with
the number of users (1 -> 500) or with group membership (0 -> 200 groups per user).
`selectinload` batches the group load into one statement rather than degrading to one per group,
so the 2 does not become 2 + G. `test_admin_check_is_constant_in_group_count` guards that.

**Wall time is flat in user count and mildly sensitive to group count.** Going from 0 to 200
groups per user adds roughly 1 ms to a session request (~1.3 ms -> ~2.4 ms on SQLite,
~1.5 ms -> ~3.1 ms on PostgreSQL) at an unchanged 2 statements — that is row and entity
materialization inside the second query, not extra round trips. Growing from 1 to 500 users
changes nothing measurable, as the unique index on `users.username` predicts.

**Basic auth was ~25x more expensive than session or bearer, and it was not the database.** At
T0 a basic-auth request cost ~50 ms against both databases, of which a directly measured
**48.2 ms was `check_password_hash`** — Werkzeug's `scrypt:32768:8:1`. The 3 SQL statements were
noise beside it.

This was fixed in #336, after the baseline was taken. Nothing in this plugin stores a
human-chosen password: every value in `users.password_hash` comes from `generate_token()`
(24 characters, 62-character alphabet, ~143 bits of entropy), and no endpoint accepts an
operator-supplied one. A memory-hard KDF exists to make brute-forcing *low-entropy* passwords
expensive, so against 143 bits it bought nothing. New hashes use
`pbkdf2:sha256:1000` (`TOKEN_HASH_METHOD` in `repository/user.py`), taking a basic-auth request
from **50.98 ms to 2.81 ms median** — into the same range as session and bearer — at an unchanged
3 statements.

Hashes written before that change keep verifying under their original method and are never
re-hashed in place, so a deployment that upgrades and rotates nothing still pays the old ~50 ms
until its tokens are rotated. Measure that path with `--hash-method scrypt:32768:8:1`.

## Caveats

- Wall times are from one machine with a local database. Treat the *statement counts* as the
  portable result and the timings as indicative.
- Statement counts transfer between dialects; query *plans* do not. Nothing here is a claim
  about the PostgreSQL planner.
- `OIDC_PROVISION_ON_BEARER_AUTH` is off, as it is by default. With it on, a bearer request adds
  a `has_user` check — one more statement on every bearer request, not just the first.
- The benchmark does not mount MLflow's Flask app, so it excludes the Flask `before_request`
  authorization hooks. Those are a separate budget, measured by `test_query_counts.py` (#253).
