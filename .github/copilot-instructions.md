# MLflow OIDC Auth Plugin - AI Coding Agent Instructions

## Project Overview

MLflow plugin that adds OIDC-based authentication to MLflow Tracking Server using a **hybrid FastAPI + Flask architecture**. FastAPI handles auth/permissions APIs and wraps the official MLflow Flask app via WSGI middleware.

### Core Architecture

```
FastAPI App (oidc_app)
├── ProxyHeadersMiddleware → parse X-Forwarded-* headers
├── AuthMiddleware → authenticates users (basic/bearer/session)
├── StarletteSessionMiddleware → manages user sessions
├── Routers (auth, permissions, UI, health, webhook, trash)
└── AuthAwareWSGIMiddleware → mounts Flask MLflow app at /
    └── MLflow Flask app (with before/after_request hooks)
```

**Key Pattern**: FastAPI authenticates → stores user in `request.state.mlflow_oidc_auth` → passes to Flask via WSGI `environ['mlflow_oidc_auth.username']` → Flask hooks enforce permissions.

## Critical Concepts

### 1. Permission System (4-level hierarchy)
- **READ** (priority 1): read-only
- **EDIT** (priority 2): read + update  
- **MANAGE** (priority 3): full control (read + update + delete + manage)
- **NO_PERMISSIONS** (priority 100): no access

Configured via `PERMISSION_SOURCE_ORDER=user,group,regex,group-regex` – system checks sources in order, stops at first match, falls back to `DEFAULT_MLFLOW_PERMISSION=MANAGE`.

**Implementation**: [mlflow_oidc_auth/utils/permissions.py](mlflow_oidc_auth/utils/permissions.py) iterates sources using source-specific config functions; [mlflow_oidc_auth/permissions.py](mlflow_oidc_auth/permissions.py) defines `Permission` dataclass with capability flags (`can_read`, `can_update`, `can_delete`, `can_manage`).

**Supports**: experiments, registered models, prompts, and scorers with separate permission tables per resource type.

### 2. Authentication Flow
1. `AuthMiddleware` ([middleware/auth_middleware.py](mlflow_oidc_auth/middleware/auth_middleware.py)) tries in order:
   - **Basic auth**: extracts base64 credentials → validates against `store.authenticate_user(username, password)`
   - **Bearer token**: validates JWT via `validate_token()` (includes JWKS refresh on `BadSignatureError`)
   - **Session**: reads username from session cookie
2. Sets `request.state.mlflow_oidc_auth = {"username": username, "is_admin": is_admin}`
3. `AuthAwareWSGIMiddleware` ([middleware/auth_aware_wsgi_middleware.py](mlflow_oidc_auth/middleware/auth_aware_wsgi_middleware.py)) creates `AuthInjectingWSGIApp` wrapper that injects auth info into WSGI `environ` before calling Flask
4. Flask hooks ([hooks/before_request.py](mlflow_oidc_auth/hooks/before_request.py), [hooks/after_request.py](mlflow_oidc_auth/hooks/after_request.py)) enforce permissions by checking `environ['mlflow_oidc_auth.username']` and validating against protobuf message types

### 3. Data Store Pattern
- **Single `store` singleton**: `from mlflow_oidc_auth.store import store`
- Backed by `SqlAlchemyStore` initialized with `OIDC_USERS_DB_URI` (SQLite/PostgreSQL/MySQL)
- Manages: users, groups, permissions (experiments, registered models, prompts, scorers)
- **Critical rule**: All routers and services use this singleton – **never instantiate new stores**
- Initialization at import time: [mlflow_oidc_auth/store.py](mlflow_oidc_auth/store.py) calls `store.init_db(config.OIDC_USERS_DB_URI)`

### 4. GraphQL Authorization
MLflow serves `/graphql` – we patch it at runtime via `install_mlflow_graphql_authorization_middleware()` in [graphql/patch.py](mlflow_oidc_auth/graphql/patch.py):
- Replaces `mlflow.server.handlers._get_graphql_auth_middleware` to return `[GraphQLAuthorizationMiddleware()]`
- Works even when `mlflow.server.auth` module is absent
- Middleware enforces per-field authorization in Graphene execution chain

### 5. WSGI-ASGI Bridge
`AuthAwareWSGIMiddleware` uses `asgiref.wsgi.WsgiToAsgi` (not deprecated Starlette WSGI middleware):
1. Creates per-request `AuthInjectingWSGIApp(flask_app, scope)` wrapper
2. Wrapper's `__call__(environ, start_response)` injects auth from ASGI `scope` into WSGI `environ`
3. Calls Flask app with enhanced environ containing `mlflow_oidc_auth.username` and `mlflow_oidc_auth.is_admin`

## Development Workflows

### Local Development
```bash
./scripts/run-dev-server.sh  # Sets up venv, installs deps, runs server with uvicorn --reload
```
- **Backend**: auto-reloads via uvicorn on Python file changes
- **Frontend**: runs `yarn --cwd web-react watch` for React UI (Vite build with watch mode)
- **Requirements**: Node.js ^14.15.0 || >=16.10.0 and yarn (checked by script)
- **Server**: `mlflow server --app-name oidc-auth --host 0.0.0.0 --port 8080 --backend-store-uri=sqlite:///mlflow.db`
- Script waits for server to be ready (polls `localhost:8080/`) before starting UI build

### Testing
```bash
pytest mlflow_oidc_auth/tests/  # Unit tests
pytest -m integration           # Integration tests (requires server)
```
- Test structure: organized by module (e.g., `test_auth.py`, `test_permissions.py`, `test_sqlalchemy_store.py`)
- Integration tests in `mlflow_oidc_auth/tests/integration/`
- Uses `pytest-asyncio` for async tests (mode set to `"auto"` in [pyproject.toml](pyproject.toml))

### Database Migrations
Uses Alembic: [mlflow_oidc_auth/db/migrations/](mlflow_oidc_auth/db/migrations/)
- Configured via `alembic.ini` in migrations directory
- Table name customizable via `OIDC_ALEMBIC_VERSION_TABLE` env var
- Auto-applied on store initialization in `SqlAlchemyStore.init_db()`

## Code Conventions

### Routers ([mlflow_oidc_auth/routers/](mlflow_oidc_auth/routers/))
- Organized by resource: `auth.py`, `users.py`, `experiment_permissions.py`, `registered_model_permissions.py`, `prompt_permissions.py`, `scorers_permissions.py`, `group_permissions.py`, `user_permissions.py`, `health.py`, `trash.py`, `ui.py`, `webhook.py`
- All exported via `get_all_routers()` in [routers/__init__.py](mlflow_oidc_auth/routers/__init__.py)
- Use FastAPI dependency injection: `from mlflow_oidc_auth.dependencies import check_admin_permission, get_current_user`
- All routers use `/oidc/` prefix (configured in `_prefix.py`)

### Configuration
- Environment-driven via `.env` and [config.py](mlflow_oidc_auth/config.py)
- Key vars:
  - **OIDC**: `OIDC_DISCOVERY_URL`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`, `OIDC_REDIRECT_URI`, `OIDC_SCOPE`
  - **Permissions**: `PERMISSION_SOURCE_ORDER`, `DEFAULT_MLFLOW_PERMISSION`
  - **Database**: `OIDC_USERS_DB_URI`, `OIDC_ALEMBIC_VERSION_TABLE`
  - **Groups**: `OIDC_GROUP_NAME`, `OIDC_ADMIN_GROUP_NAME`, `OIDC_GROUPS_ATTRIBUTE`
  - **UI**: `EXTEND_MLFLOW_MENU`, `DEFAULT_LANDING_PAGE_IS_PERMISSIONS`
- `OIDC_REDIRECT_URI` supports dynamic proxy path detection if unset (uses X-Forwarded headers)
- Boolean env vars parsed via `get_bool_env_variable()` (accepts "true", "1", "t")

### Middleware Ordering (critical!)
```python
ProxyHeadersMiddleware      # Parse X-Forwarded-* headers FIRST (for proxy support)
AuthMiddleware             # Authenticate user (basic/bearer/session)
StarletteSessionMiddleware # Session management (requires SECRET_KEY)
```
**Order matters**: ProxyHeadersMiddleware must run before AuthMiddleware to correctly detect redirect URIs behind proxies.

### UI Integration
- MLflow UI extended via `hack.py` – reads `mlflow.server.app.static_folder/index.html` and injects `hack/menu.html` before `</body>` tag
- Enabled when `EXTEND_MLFLOW_MENU=True` (default)
- Replaces `mlflow.server.app.view_functions["serve"]` in `create_app()` to use patched handler
- React UI in [web-react/](web-react/) built separately with Vite (TypeScript + React 19)

### Python Style
- **Line length**: 160 characters (see [pyproject.toml](pyproject.toml))
- **Formatting**: Black (configured for 160 chars)
- **Type hints**: Required for all function parameters and returns (PEP 484)
- **Docstrings**: PEP 257 format with Parameters/Returns sections
- See [.github/instructions/python.instructions.md](.github/instructions/python.instructions.md) for full conventions

## Migration Context (Flask → FastAPI)

**Current state**: Hybrid architecture – FastAPI for new APIs, Flask for MLflow compatibility.

**When adding features**:
- New APIs → FastAPI routers (see examples in [routers/](mlflow_oidc_auth/routers/))
- Avoid Flask imports in new code (exception: hooks in [hooks/](mlflow_oidc_auth/hooks/))
- Use FastAPI middleware patterns, not Flask hooks
- Prefer FastAPI dependency injection (`Depends`) over Flask `g` object
- Use `request.state.mlflow_oidc_auth` for auth info, not Flask session

**Do not modify** the Flask app mount or hooks unless necessary – they provide compatibility with MLflow's existing UI/API.

## Common Patterns

### Adding a permission check
```python
from mlflow_oidc_auth.utils.permissions import get_permission_for_resource

permission = get_permission_for_resource(
    username="user@example.com",
    resource_type="experiment",  # or "registered_model", "prompt", "scorer"
    resource_name="my-experiment"  # experiment ID or model name
)
if not permission.can_update:
    raise HTTPException(403, "Insufficient permissions")
```

### Adding a router
1. Create file in `mlflow_oidc_auth/routers/my_feature.py`
2. Define `my_feature_router = APIRouter(prefix="/oidc/my-feature", tags=["my-feature"])`
3. Add to `get_all_routers()` in [routers/__init__.py](mlflow_oidc_auth/routers/__init__.py)
4. Include router in `__all__` list for proper exports

### Accessing authenticated user
```python
from fastapi import Request, HTTPException

async def my_endpoint(request: Request):
    auth_info = request.state.mlflow_oidc_auth  # Dict[str, Any]
    username = auth_info.get("username")
    is_admin = auth_info.get("is_admin", False)
    
    if not username:
        raise HTTPException(401, "Not authenticated")
```

### Using dependencies
```python
from fastapi import Depends
from mlflow_oidc_auth.dependencies import check_admin_permission

@router.post("/admin-only")
async def admin_endpoint(username: str = Depends(check_admin_permission)):
    # username is already validated as admin
    pass
```

## External Dependencies

- **MLflow**: Mounted as Flask WSGI app – version `>=3.8.1,<4` in [pyproject.toml](pyproject.toml)
- **Authlib**: OIDC client library (JWT validation with JWKS)
- **SQLAlchemy**: Database ORM `>=1.4.0,<3` (supports SQLite, PostgreSQL, MySQL)
- **FastAPI**: `>=0.100.0` for async API framework
- **Uvicorn**: `>=0.20.0` ASGI server with reload support
- **asgiref**: `>=3.0.0` WSGI-to-ASGI adapter (replaces deprecated Starlette WSGI)
- **Alembic**: `<2,!=1.10.0` for database migrations
- **React 19**: Frontend UI with Vite bundler and TypeScript

## References

- Permission system details: [docs/permissions.md](docs/permissions.md)
- Configuration guide: [docs/configuration.md](docs/configuration.md)  
- Development guide: [docs/development.md](docs/development.md)
- Python style guide: [.github/instructions/python.instructions.md](.github/instructions/python.instructions.md)
