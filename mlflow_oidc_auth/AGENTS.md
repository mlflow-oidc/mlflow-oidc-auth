# AGENTS.md — backend (`mlflow_oidc_auth/`)

Extends the [root AGENTS.md](../AGENTS.md). Applies to everything under `mlflow_oidc_auth/`.

## Where things live

| Concern | Location |
|---|---|
| FastAPI app factory, middleware wiring, Flask mount | `app.py` |
| Authentication (Basic / Bearer / session) | `middleware/auth_middleware.py` |
| JWT + JWKS validation | `auth.py` |
| OIDC client registration | `oauth.py` |
| Route → validator mapping for MLflow's API | `hooks/before_request.py` |
| Grant-on-create, search filtering, cascades | `hooks/after_request.py` |
| Per-resource permission checks | `validators/` |
| Data access facade | `store.py` → `sqlalchemy_store.py` → `repository/` |
| ORM models (`Sql*`) | `db/models/` · migrations in `db/migrations/versions/` |
| Domain entities (plain classes) | `entities/` |
| Pydantic request/response models | `models/` |
| FastAPI endpoints | `routers/` · auth gates in `dependencies.py` |
| Config + secret providers | `config.py`, `config_providers/` |

## Adding a router

1. `routers/my_feature.py` with `my_feature_router = APIRouter(tags=["my-feature"])`.
2. Register in `get_all_routers()` in `routers/__init__.py`.
3. Gate every endpoint with a dependency — never check permissions inline:

```python
from mlflow_oidc_auth.dependencies import check_admin_permission

@my_feature_router.post("/admin-only")
async def endpoint(username: str = Depends(check_admin_permission)):
    ...  # username is already validated
```

## Adding coverage for a new MLflow API surface

An MLflow route with no entry in `hooks/before_request.py` is **unauthorized by omission**. When
MLflow adds RPCs:

1. Map the protobuf request class → a validator in `hooks/before_request.py`.
2. Implement the validator in `validators/`, resolving permission through the store.
3. If the RPC creates a resource, add the grant-on-create path in `hooks/after_request.py`.
4. If it lists resources, add search filtering — an unfiltered list leaks across tenants.
5. Add a **negative** test: a user without permission is denied.

## Permissions

Levels `READ` < `USE` < `EDIT` < `MANAGE`, plus `NO_PERMISSIONS` (explicit denial).
Resolution order comes from `PERMISSION_SOURCE_ORDER` (default `user,group,regex,group-regex`);
first match wins, then `DEFAULT_MLFLOW_PERMISSION`. Admins bypass checks — so any code path that
sets `is_admin` is security-critical.

## Tests

- Live in `mlflow_oidc_auth/tests/`, mirroring the package layout.
- **Do not run the whole `hooks/` directory locally** — `test_after_request.py` hangs. Run per file.
- Every auth change needs a denial test, not only a success test.
- Migration tests run forward and backward, on SQLite and PostgreSQL.
