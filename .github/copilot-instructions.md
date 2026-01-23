# MLflow OIDC Auth Plugin - AI Coding Agent Instructions

## Architecture Overview

Hybrid **FastAPI + Flask** plugin: FastAPI handles auth/permissions APIs, Flask provides MLflow compatibility via WSGI mount.

```
FastAPI App → ProxyHeadersMiddleware → AuthMiddleware → SessionMiddleware
    ├── /oidc/* routers (auth, permissions, UI, health)
    └── AuthAwareWSGIMiddleware → Flask MLflow app (with before/after_request hooks)
```

**Auth flow**: FastAPI authenticates → `request.state.mlflow_oidc_auth` → WSGI `environ['mlflow_oidc_auth.username']` → Flask hooks enforce permissions.

## Critical Rules

1. **Store singleton**: Always `from mlflow_oidc_auth.store import store` – never instantiate new stores
2. **New APIs → FastAPI**: Add routers to [routers/](mlflow_oidc_auth/routers/), use `Depends()` for auth
3. **Middleware order matters**: Proxy → Auth → Session (see [app.py](mlflow_oidc_auth/app.py))
4. **Don't modify Flask hooks** unless necessary – they ensure MLflow UI/API compatibility

## Permission System

4 levels: `READ` < `EDIT` < `MANAGE` < `NO_PERMISSIONS` (denial)

Source order via `PERMISSION_SOURCE_ORDER=user,group,regex,group-regex` – first match wins, falls back to `DEFAULT_MLFLOW_PERMISSION`.

```python
# Check permissions (supports experiment, registered_model, prompt, scorer)
from mlflow_oidc_auth.utils.permissions import get_permission_for_experiment
permission = get_permission_for_experiment(experiment_id, username)
if not permission.can_update:
    raise HTTPException(403, "Insufficient permissions")
```

## Development

```bash
./scripts/run-dev-server.sh  # Starts backend + React UI with hot reload
pytest mlflow_oidc_auth/tests/  # Unit tests
pytest -m integration           # Integration tests (requires running server)
```

## Adding a Router

1. Create `mlflow_oidc_auth/routers/my_feature.py` with `my_feature_router = APIRouter(tags=["my-feature"])`
2. Add to `get_all_routers()` in [routers/__init__.py](mlflow_oidc_auth/routers/__init__.py)
3. Use dependency injection for auth:

```python
from mlflow_oidc_auth.dependencies import check_admin_permission, get_username

@router.post("/admin-only")
async def endpoint(username: str = Depends(check_admin_permission)):
    pass  # username already validated as admin
```

## Key Files

- [app.py](mlflow_oidc_auth/app.py) – FastAPI factory, middleware setup, Flask mount
- [store.py](mlflow_oidc_auth/store.py) – Database singleton (SqlAlchemy)
- [middleware/auth_middleware.py](mlflow_oidc_auth/middleware/auth_middleware.py) – Basic/Bearer/Session auth
- [utils/permissions.py](mlflow_oidc_auth/utils/permissions.py) – Permission resolution logic
- [hooks/](mlflow_oidc_auth/hooks/) – Flask request hooks for MLflow API authorization

## Style

- **Python**: Black @ 160 chars, type hints required, PEP 257 docstrings (see [python.instructions.md](.github/instructions/python.instructions.md))
- **React**: TypeScript + Tailwind in [web-react/](web-react/) (see [react.instructions.md](.github/instructions/react.instructions.md))
