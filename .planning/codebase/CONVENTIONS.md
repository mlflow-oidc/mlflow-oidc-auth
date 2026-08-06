# Coding Conventions

**Analysis Date:** 2026-03-23

## Naming Patterns

**Python Files:**
- Use `snake_case.py` for all modules: `experiment_permissions.py`, `sqlalchemy_store.py`
- Prefix SQLAlchemy ORM models with `Sql`: `SqlUser`, `SqlExperimentPermission`, `SqlGroup`
- Prefix entity dataclasses/classes without prefix: `User`, `ExperimentPermission`, `Group`
- Prefix Pydantic models descriptively: `CreateAccessTokenRequest`, `WebhookUpdateRequest`, `ExperimentSummary`
- Test files use `test_` prefix: `test_config.py`, `test_sqlalchemy_store.py`
- Private functions use `_` prefix: `_get_permission_from_experiment_id()`, `_parse_optional_datetime()`

**Python Functions:**
- Use `snake_case` for all functions and methods
- Validator functions follow `validate_can_<action>_<resource>` pattern: `validate_can_read_experiment()`
- Getter functions follow `get_<thing>` pattern: `get_username()`, `get_is_admin()`, `get_logger()`
- Router endpoint functions are `async` and use descriptive names: `async def get_experiment_users()`
- FastAPI dependency functions follow `check_<resource>_<permission>_permission` pattern: `check_admin_permission()`, `check_experiment_manage_permission()`

**Python Variables:**
- Use `snake_case` for local and module-level variables
- Configuration constants use `UPPER_SNAKE_CASE`: `DEFAULT_MLFLOW_PERMISSION`, `OIDC_CLIENT_SECRET`
- Module-level logger instance: `logger = get_logger()`

**Python Classes:**
- Use `PascalCase`: `AppConfig`, `SqlAlchemyStore`, `AuthMiddleware`
- Entities are plain classes with properties: `User`, `ExperimentPermission`
- DB models inherit from `Base`: `class SqlUser(Base)`
- Pydantic models inherit from `BaseModel`: `class CreateUserRequest(BaseModel)`

**React/TypeScript Files:**
- Use `kebab-case.tsx` for components: `auth-page.tsx`, `loading-spinner.tsx`, `dark-mode-toggle.tsx`
- Use `kebab-case.ts` for non-component modules: `http.ts`, `runtime-config.ts`
- Use `kebab-case.test.tsx` / `kebab-case.test.ts` for tests (co-located with source)
- Use `use-<name>.ts` for hooks: `use-auth.ts`, `use-search.ts`, `use-api.ts`

**React Functions/Components:**
- Use `PascalCase` for components: `AuthPage`, `LoadingSpinner`, `MainLayout`
- Use `camelCase` for hook names: `useRuntimeConfig`, `useAuthErrors`, `useSearch`
- Use `camelCase` for utility functions: `buildUrl`, `http`

**React Types:**
- Use `PascalCase` for types and interfaces: `RuntimeConfig`, `RequestOptions`
- Types are typically co-located in `types/` directories within `core/`, `shared/`, or feature dirs

## Code Style

**Python Formatting:**
- **Black** formatter with line-length 160 (configured in `pyproject.toml` `[tool.black]`)
- Enforced via pre-commit hook (`.pre-commit-config.yaml`)
- Python 3.12 target (`.python-version`)

**TypeScript/React Formatting:**
- **Prettier** with configuration in `web-react/.prettierrc`:
  - `semi: true` (semicolons required)
  - `tabWidth: 2`
  - `printWidth: 80`
  - `trailingComma: "all"`
  - `bracketSpacing: true`

**EditorConfig** (`.editorconfig`):
- UTF-8 charset
- Space indentation, default indent size 2
- LF line endings
- Insert final newline, trim trailing whitespace
- JS/TS/JSON/CSS/HTML/MD/YAML files: indent size 2

**Linting:**

*Python:*
- **Black** (formatting only, via pre-commit)
- **Bandit** (security analysis, via GitHub Actions on `mlflow_oidc_auth/**` paths)
  - Severity: high, Confidence: high
- **autoflake** available as dev dependency but not in pre-commit hooks

*TypeScript/React:*
- **ESLint** configured in `web-react/eslint.config.js`:
  - Extends: `js.configs.recommended`, `tseslint.configs.recommendedTypeChecked`
  - React plugins: `react-hooks`, `react-x`, `react-dom`, `react-refresh`
  - `eslint-config-prettier` to avoid formatting conflicts
  - Custom rule: unused vars with `^_` ignore pattern
- **TypeScript** strict mode enabled in `web-react/tsconfig.app.json`:
  - `strict: true`
  - `noUnusedLocals: true`
  - `noUnusedParameters: true`
  - `noFallthroughCasesInSwitch: true`
  - `verbatimModuleSyntax: true`

## Pre-commit Hooks

Defined in `.pre-commit-config.yaml`:

1. **check-yaml** - Validates YAML syntax
2. **check-added-large-files** - Max 800KB per file
3. **detect-private-key** - Prevents committing private keys
4. **end-of-file-fixer** - Ensures files end with newline
5. **trailing-whitespace** - Removes trailing whitespace
6. **mixed-line-ending** - Enforces consistent line endings
7. **check-toml** - Validates TOML syntax
8. **black** - Python code formatting (v26.1.0)

Run in CI via `.github/workflows/pre-commit.yml` on pull requests.

## Import Organization

**Python:**

Imports are organized in this order (follow standard Python convention):
1. Standard library imports (`import os`, `from datetime import datetime`)
2. Third-party imports (`from fastapi import APIRouter`, `from sqlalchemy import ...`)
3. Local/project imports (`from mlflow_oidc_auth.config import config`)

Within project imports, use absolute imports from `mlflow_oidc_auth`:
```python
from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.store import store
from mlflow_oidc_auth.entities import User, ExperimentPermission
```

Relative imports are used only for sibling modules in the same package:
```python
from ._prefix import EXPERIMENT_PERMISSIONS_ROUTER_PREFIX
```

Each module directory has an `__init__.py` with explicit `__all__` exports. Package `__init__.py` files re-export key symbols for convenient imports:
```python
# mlflow_oidc_auth/models/__init__.py
from mlflow_oidc_auth.models.user import CreateAccessTokenRequest, CreateUserRequest
```

**TypeScript/React:**

Imports are organized:
1. Third-party library imports (`import React from "react"`, `import { vi } from "vitest"`)
2. Relative project imports using `../../` paths (no path aliases configured)

Example:
```typescript
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { useRuntimeConfig } from "../../shared/context/use-runtime-config";
import { useAuthErrors } from "./hooks/use-auth-errors";
```

No path aliases (like `@/`) are configured. All imports use relative paths.

## Error Handling

**Python - FastAPI (primary pattern):**

FastAPI routers raise `HTTPException` with appropriate status codes:
```python
from fastapi import HTTPException

raise HTTPException(status_code=403, detail="Administrator privileges required for this operation")
raise HTTPException(status_code=404, detail="Resource not found")
```

FastAPI dependency functions use try/except around authentication checks:
```python
async def check_admin_permission(request: Request) -> str:
    try:
        username = await get_username(request=request)
        is_admin = await get_is_admin(request=request)
    except Exception:
        raise HTTPException(status_code=403, detail="Administrator privileges required")
```

**Python - MLflow exception handling:**

MLflow exceptions are caught by a registered exception handler in `mlflow_oidc_auth/exceptions.py`:
```python
# Maps MLflow error codes to HTTP status codes:
# RESOURCE_ALREADY_EXISTS → 409
# RESOURCE_DOES_NOT_EXIST → 404
# INVALID_PARAMETER_VALUE → 400
# UNAUTHORIZED / UNAUTHENTICATED → 401
# PERMISSION_DENIED → 403
# Unknown → 500 (default)
```

Response format is JSON with `error_code`, `message`, and `details` fields.

**Python - Flask legacy responses:**

Flask responses in `mlflow_oidc_auth/responses/client_error.py`:
```python
def make_auth_required_response() -> Response:    # 401
def make_forbidden_response(msg=None) -> Response: # 403
def make_basic_auth_response() -> Response:        # 401 with WWW-Authenticate header
```

**Python - Repository layer:**

SQLAlchemy exceptions are caught and re-raised as `MlflowException`:
```python
from mlflow.exceptions import MlflowException
# IntegrityError → MlflowException("... already exists", error_code="RESOURCE_ALREADY_EXISTS")
# NoResultFound → MlflowException("... not found", error_code="RESOURCE_DOES_NOT_EXIST")
```

**TypeScript/React:**

HTTP errors throw generic `Error` with status details:
```typescript
if (!res.ok) {
    const text = await res.text();
    throw new Error(`HTTP ${res.status}: ${text}`);
}
```

## Type Annotations

**Python:**
- Type hints used in function signatures for public APIs and dependencies:
  ```python
  def get_bool_env_variable(variable: str, default_value: bool) -> bool:
  async def check_admin_permission(request: Request) -> str:
  def get_all_routers() -> List[APIRouter]:
  ```
- Entity classes use properties without type annotations (legacy pattern)
- Pydantic models use field type annotations:
  ```python
  class CreateUserRequest(BaseModel):
      username: str
      display_name: str
      is_admin: bool = False
  ```
- SQLAlchemy ORM models use `Mapped[T]` type annotations:
  ```python
  id: Mapped[int] = mapped_column(Integer(), primary_key=True)
  username: Mapped[str] = mapped_column(String(255), unique=True)
  ```
- `typing` module used: `List`, `Optional`, `Any`, `Dict`, `AsyncIterator`
- Modern `X | None` union syntax used in some newer files (e.g., `mlflow_oidc_auth/entities/user.py`)

**TypeScript/React:**
- Strict TypeScript (`strict: true` in tsconfig)
- Generic types used for HTTP: `async function http<T = unknown>(url: string, ...): Promise<T>`
- Vitest `Mock` type for typed test mocks: `const mockUseAuthErrors: Mock<() => string[]> = vi.fn()`
- React component props typed inline or via type parameters

## Documentation Patterns

**Python Module Docstrings:**
- Every module starts with a triple-quoted docstring describing purpose:
  ```python
  """
  FastAPI application factory for MLflow OIDC Auth Plugin.

  This module provides a FastAPI application factory that can be used as an alternative
  to the default MLflow server when OIDC authentication is required.
  """
  ```

**Python Function/Method Docstrings:**
- Use Google/Sphinx hybrid style with `Parameters`, `Returns`, `Raises`:
  ```python
  def check_admin_permission(request: Request) -> str:
      """
      Verify that the current user has administrator privileges.

      Parameters:
      -----------
      request : Request
          The FastAPI request object containing session information.

      Returns:
      --------
      str
          The username of the authenticated admin user.

      Raises:
      -------
      HTTPException
          If the user is not authenticated.
      """
  ```
- Inline comments for important logic or TODO items

**Python Test Docstrings:**
- Test classes have docstrings describing the test group
- Individual test methods have one-line docstrings describing the scenario:
  ```python
  def test_get_oidc_jwks_success(self, mock_config, mock_requests):
      """Test successful JWKS retrieval from OIDC provider"""
  ```

**TypeScript:**
- No JSDoc/TSDoc convention enforced
- Minimal inline comments

## Git Conventions

**Commit Messages:**
- **Conventional Commits** required, enforced by CI
- Pattern: `^(feat|fix|chore|docs|style|ci|refactor|perf|test|build)(\([\w-]+\))?:\s.+$`
- Types: `feat`, `fix`, `chore`, `docs`, `style`, `ci`, `refactor`, `perf`, `test`, `build`

**PR Titles:**
- Must follow Conventional Commits format (enforced by `.github/workflows/pr-validate-title.yml`)
- Subject must NOT start with uppercase letter
- Scope is optional: `feat(auth): add token refresh`

**Branches:**
- `main` - production releases
- `rc` - release candidate (pre-release channel)
- Semantic release via `.releaserc` with `@semantic-release/commit-analyzer`

**Release Process:**
- Automated via semantic-release on push to `main`
- Builds Python wheel and publishes to PyPI
- Uses `@semantic-release/exec` with `scripts/release.sh` for version bumping
- React UI is built during release (`vite build` outputs to `mlflow_oidc_auth/ui/`)

## Logging

**Framework:** Python `logging` module via custom `get_logger()` in `mlflow_oidc_auth/logger.py`

**Patterns:**
- Singleton logger: `logger = get_logger()` at module level
- Logger defaults to `uvicorn` logger name (for FastAPI compatibility)
- Log level configurable via `LOG_LEVEL` environment variable
- Format: `%(asctime)s %(levelname)s %(name)s: %(message)s`
- Use `logger.info()`, `logger.warning()`, `logger.error()` for operational messages

## Module Design

**Exports:**
- All packages use `__init__.py` with explicit `__all__` lists
- Re-export key symbols from submodules for convenient importing

**Architecture Layers:**
- `routers/` - FastAPI route handlers (thin layer, delegates to store)
- `dependencies.py` - FastAPI dependency injection functions
- `validators/` - Permission validation logic (Flask request context)
- `store.py` / `sqlalchemy_store.py` - Data access via repository pattern
- `repository/` - SQLAlchemy repository classes
- `entities/` - Domain entity classes (plain Python)
- `db/models/` - SQLAlchemy ORM model classes (prefixed `Sql`)
- `models/` - Pydantic request/response models
- `responses/` - Flask response helpers (legacy)
- `middleware/` - FastAPI and ASGI middleware
- `config.py` - Configuration management via `AppConfig` singleton
- `config_providers/` - Pluggable configuration source providers
- `utils/workspace_cache.py` - TTL-based workspace permission cache

**Workspace Permission Check Pattern:**
- Workspace enforcement points must always check `perm is not None and perm.can_read` (or `perm.can_manage`), never just `perm is not None`. This is because `NO_PERMISSIONS` is a valid permission object with `can_read=False`.
- Example:
  ```python
  perm = get_workspace_permission_cached(username, workspace_name)
  if perm is not None and perm.can_read:
      # user has access
  ```

---

*Convention analysis: 2026-03-23*
