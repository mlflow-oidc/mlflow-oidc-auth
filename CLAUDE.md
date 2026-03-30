<!-- GSD:project-start source:PROJECT.md -->
## Project

**MLflow OIDC Auth — Organization Support**

An MLflow authentication and authorization plugin (mlflow-oidc-auth) that adds OIDC-based login, RBAC with users/groups, and per-resource permission management to MLflow tracking servers. The project is adding multi-tenant organization support, aligning with MLflow 3.10's new organization features, to enable resource isolation across teams or external organizations sharing a single MLflow instance.

**Core Value:** Multi-tenant resource isolation — organizations must be able to share an MLflow instance while each tenant sees only their own experiments, models, and resources, with no accidental data leakage between tenants.

### Constraints

- **Compatibility**: Must target MLflow >=3.10.0 — org features require 3.10 baseline
- **Production impact**: Existing deployments must have a clear migration path, even if major version bump
- **Tech stack**: Python/FastAPI/Flask/SQLAlchemy backend, React/TypeScript frontend — no new frameworks
- **Plugin boundary**: Can only control auth/authz — cannot modify MLflow core behavior
- **Research dependency**: Implementation scope gated on research findings about MLflow 3.10 internals
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages
- Python 3.12 - Backend server, auth plugin, CLI, database models, API routers (`.python-version`, CI uses `python-version: 3.12`)
- TypeScript ~5.9 - React frontend UI (`web-react/package.json`)
- SQL - Database migrations via Alembic (`mlflow_oidc_auth/db/migrations/`)
- Bash - Dev/release scripts (`scripts/release.sh`, `scripts/run-dev-server.sh`)
- YAML - CI/CD workflows, Docker Compose (`scripts/docker-compose.yaml`, `.github/workflows/`)
## Runtime
- Python >=3.10 (declared in `pyproject.toml`), 3.12 used in development/CI
- Tox test matrix targets `py314` (`tox.ini` envlist)
- Node 24 (CI uses `node-version: 24` in `.github/workflows/unit-tests.yml`)
- ES modules (`"type": "module"` in `web-react/package.json`)
- pip + setuptools for Python (`pyproject.toml` build-system)
- Yarn for JavaScript (`web-react/yarn.lock` present)
- Lockfile: `web-react/yarn.lock` present; no Python lockfile (pip freeze / tox managed)
## Frameworks
- FastAPI >=0.132.0 - Primary ASGI application framework (`pyproject.toml`, `mlflow_oidc_auth/app.py`)
- Flask <4 - MLflow's built-in web framework, mounted as WSGI under FastAPI (`mlflow_oidc_auth/app.py`)
- Starlette - Underlying ASGI framework (via FastAPI), session middleware (`starlette.middleware.sessions`)
- MLflow >=3.10.0, <4 - ML experiment tracking server; this project is an auth plugin (`pyproject.toml`)
- React 19.1 - UI framework (`web-react/package.json`)
- React Router 7.9 - Client-side routing (`web-react/package.json`)
- Tailwind CSS 4 - Utility-first CSS framework (`@tailwindcss/vite` plugin in `web-react/package.json`)
- FontAwesome 7 - Icon library (`@fortawesome/*` packages)
- pytest >=8.3.2 - Python test runner (`pyproject.toml`)
- pytest-asyncio <2 - Async test support, mode `auto` (`pyproject.toml`)
- pytest-cov >=5.0.0 - Coverage reporting (`pyproject.toml`)
- Vitest 4.0 - JavaScript test runner (`web-react/package.json`)
- Testing Library (React 16, DOM 10, jest-dom 6, user-event 14) - React component testing
- jsdom 27 - Browser environment for Vitest (`web-react/vite.config.ts`)
- Playwright - Integration/E2E browser tests (`tox.ini` integration env)
- Vite (rolldown-vite 7.3.1) - Frontend build tool, aliased via `npm:rolldown-vite@7.3.1` (`web-react/package.json`)
- SWC - Fast React compilation via `@vitejs/plugin-react-swc` (`web-react/vite.config.ts`)
- setuptools - Python build backend (`pyproject.toml`)
- tox - Test environment management (`tox.ini`)
- pre-commit - Git hooks for code quality (`.pre-commit-config.yaml`)
- semantic-release - Automated versioning and release (`.releaserc`)
## Key Dependencies
- `mlflow` >=3.10.0, <4 - Core tracking server this plugin extends (`pyproject.toml`)
- `fastapi` >=0.132.0 - ASGI web framework for auth routes (`pyproject.toml`)
- `uvicorn` >=0.41.0 - ASGI server (`pyproject.toml`)
- `authlib` <2 - OIDC/OAuth2 client library, JWT validation (`mlflow_oidc_auth/oauth.py`, `mlflow_oidc_auth/auth.py`)
- `sqlalchemy` >=2.0.46, <3 - ORM for auth database (`mlflow_oidc_auth/sqlalchemy_store.py`)
- `alembic` <2, !=1.18.4 - Database migrations (`mlflow_oidc_auth/db/utils.py`)
- `flask` <4 - MLflow's web layer, hooks registered directly (`mlflow_oidc_auth/app.py`)
- `requests` >=2.32.5, <3 - HTTP client for OIDC discovery/JWKS (`mlflow_oidc_auth/auth.py`)
- `httpx` >=0.28.1 - Async HTTP client (`pyproject.toml`)
- `python-dotenv` <2 - `.env` file loading (`mlflow_oidc_auth/config.py`)
- `asgiref` >=3.11.1 - ASGI utilities (`pyproject.toml`)
- `gunicorn` <24 - WSGI server for non-Windows (`pyproject.toml`, platform conditional)
- `click` - CLI framework for `mlflow-oidc-server` command (`mlflow_oidc_auth/cli.py`, transitive via mlflow)
- `react` 19.1 / `react-dom` 19.1 - UI rendering
- `react-router` 7.9 - Client-side routing (devDependency in package.json but used at runtime)
- `dompurify` 3.3 - HTML sanitization
- `@fortawesome/*` 7.1 / 3.1 - Icon components
- `boto3` >=1.42.26 - AWS Secrets Manager + Parameter Store (`pyproject.toml` `[aws]` extra)
- `azure-identity` >=1.25.1, `azure-keyvault-secrets` >=4.10.0 - Azure Key Vault (`pyproject.toml` `[azure]` extra)
- `hvac` >=2.4.0 - HashiCorp Vault client (`pyproject.toml` `[vault]` extra)
- `black` >=24.8.0, <26 - Code formatter (`pyproject.toml` `[dev]` extra, `.pre-commit-config.yaml`)
- `autoflake` <2 - Unused import removal (`pyproject.toml` `[dev]` extra)
- `pre-commit` <5 - Git hook manager
- `coverage` <=7.6 - Code coverage (`tox.ini`)
- `bandit` - Security linter (`.github/workflows/bandit.yml`)
- `typescript` ~5.9 - Type checking
- `eslint` ~9.36 + plugins - Linting (`web-react/eslint.config.js`)
- `prettier` ~3.8 - Code formatting (`web-react/.prettierrc`)
- `@vitest/coverage-v8` 4.0 - Coverage reporting
## Database / Storage
- SQLAlchemy 2.x ORM with Alembic migrations (`mlflow_oidc_auth/db/`)
- Default: SQLite (`sqlite:///auth.db` per `mlflow_oidc_auth/config.py`)
- Supported: PostgreSQL, MySQL, any SQLAlchemy-compatible database
- Connection URI configured via `OIDC_USERS_DB_URI` environment variable
- Schema managed via Alembic migrations in `mlflow_oidc_auth/db/migrations/versions/`
- SQLAlchemy `DeclarativeBase` used (`mlflow_oidc_auth/db/models/_base.py`)
- Helper scripts for PostgreSQL (`scripts/postgresql/`) and MySQL (`scripts/mysql/`)
- Managed separately by MLflow (not by this plugin)
- Configured via `MLFLOW_BACKEND_STORE_URI` environment variable
- Cookie-based sessions via Starlette `SessionMiddleware` (no server-side session store)
- Signed with `SECRET_KEY` configuration value
- All replicas must share the same `SECRET_KEY` for multi-instance deployments
- Redis available via Docker Compose for cache integration testing (`scripts/docker-compose.yaml`)
## Configuration
- Primary: Environment variables (with `python-dotenv` `.env` file loading)
- Pluggable config provider chain: AWS Secrets Manager → Azure Key Vault → HashiCorp Vault → Kubernetes Secrets → AWS Parameter Store → Environment Variables (`mlflow_oidc_auth/config_providers/manager.py`)
- `AppConfig` singleton in `mlflow_oidc_auth/config.py` loads all configuration
- `pyproject.toml` - Python package metadata, build config, tool settings
- `web-react/package.json` - Frontend dependencies and scripts
- `tox.ini` - Test environment configuration
- `.pre-commit-config.yaml` - Pre-commit hook configuration
- `.releaserc` - Semantic release configuration
- `.editorconfig` - Editor formatting settings
- `sonar-project.properties` - SonarCloud configuration
- `.coveragerc` - Python coverage configuration
- `web-react/vite.config.ts` - Vite build config, outputs to `../mlflow_oidc_auth/ui`
- `web-react/tsconfig.json` + `tsconfig.app.json` + `tsconfig.node.json` - TypeScript config
- `web-react/eslint.config.js` - ESLint flat config
## Platform Requirements
- Python 3.12 (via `.python-version`)
- Node.js 24 (per CI config)
- Yarn package manager
- Optional: Docker Compose for Redis testing
- Python >=3.10 (>=3.12 recommended)
- No Node.js required (frontend is pre-built into `mlflow_oidc_auth/ui/`)
- ASGI server: uvicorn (bundled dependency)
- Database: SQLite (default) or PostgreSQL/MySQL
- PyPI package: `pip install mlflow-oidc-auth`
- Optional extras: `pip install mlflow-oidc-auth[aws]`, `[azure]`, `[vault]`, `[cloud]`
- CLI entry point: `mlflow-oidc-server` (installed via `[project.scripts]`)
- MLflow plugin entry point: `mlflow server --app-name oidc-auth` (via `[project.entry-points."mlflow.app"]`)
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Naming Patterns
- Use `snake_case.py` for all modules: `experiment_permissions.py`, `sqlalchemy_store.py`
- Prefix SQLAlchemy ORM models with `Sql`: `SqlUser`, `SqlExperimentPermission`, `SqlGroup`
- Prefix entity dataclasses/classes without prefix: `User`, `ExperimentPermission`, `Group`
- Prefix Pydantic models descriptively: `CreateAccessTokenRequest`, `WebhookUpdateRequest`, `ExperimentSummary`
- Test files use `test_` prefix: `test_config.py`, `test_sqlalchemy_store.py`
- Private functions use `_` prefix: `_get_permission_from_experiment_id()`, `_parse_optional_datetime()`
- Use `snake_case` for all functions and methods
- Validator functions follow `validate_can_<action>_<resource>` pattern: `validate_can_read_experiment()`
- Getter functions follow `get_<thing>` pattern: `get_username()`, `get_is_admin()`, `get_logger()`
- Router endpoint functions are `async` and use descriptive names: `async def get_experiment_users()`
- FastAPI dependency functions follow `check_<resource>_<permission>_permission` pattern: `check_admin_permission()`, `check_experiment_manage_permission()`
- Use `snake_case` for local and module-level variables
- Configuration constants use `UPPER_SNAKE_CASE`: `DEFAULT_MLFLOW_PERMISSION`, `OIDC_CLIENT_SECRET`
- Module-level logger instance: `logger = get_logger()`
- Use `PascalCase`: `AppConfig`, `SqlAlchemyStore`, `AuthMiddleware`
- Entities are plain classes with properties: `User`, `ExperimentPermission`
- DB models inherit from `Base`: `class SqlUser(Base)`
- Pydantic models inherit from `BaseModel`: `class CreateUserRequest(BaseModel)`
- Use `kebab-case.tsx` for components: `auth-page.tsx`, `loading-spinner.tsx`, `dark-mode-toggle.tsx`
- Use `kebab-case.ts` for non-component modules: `http.ts`, `runtime-config.ts`
- Use `kebab-case.test.tsx` / `kebab-case.test.ts` for tests (co-located with source)
- Use `use-<name>.ts` for hooks: `use-auth.ts`, `use-search.ts`, `use-api.ts`
- Use `PascalCase` for components: `AuthPage`, `LoadingSpinner`, `MainLayout`
- Use `camelCase` for hook names: `useRuntimeConfig`, `useAuthErrors`, `useSearch`
- Use `camelCase` for utility functions: `buildUrl`, `http`
- Use `PascalCase` for types and interfaces: `RuntimeConfig`, `RequestOptions`
- Types are typically co-located in `types/` directories within `core/`, `shared/`, or feature dirs
## Code Style
- **Black** formatter with line-length 160 (configured in `pyproject.toml` `[tool.black]`)
- Enforced via pre-commit hook (`.pre-commit-config.yaml`)
- Python 3.12 target (`.python-version`)
- **Prettier** with configuration in `web-react/.prettierrc`:
- UTF-8 charset
- Space indentation, default indent size 2
- LF line endings
- Insert final newline, trim trailing whitespace
- JS/TS/JSON/CSS/HTML/MD/YAML files: indent size 2
- **Black** (formatting only, via pre-commit)
- **Bandit** (security analysis, via GitHub Actions on `mlflow_oidc_auth/**` paths)
- **autoflake** available as dev dependency but not in pre-commit hooks
- **ESLint** configured in `web-react/eslint.config.js`:
- **TypeScript** strict mode enabled in `web-react/tsconfig.app.json`:
## Pre-commit Hooks
## Import Organization
## Error Handling
## Type Annotations
- Type hints used in function signatures for public APIs and dependencies:
- Entity classes use properties without type annotations (legacy pattern)
- Pydantic models use field type annotations:
- SQLAlchemy ORM models use `Mapped[T]` type annotations:
- `typing` module used: `List`, `Optional`, `Any`, `Dict`, `AsyncIterator`
- Modern `X | None` union syntax used in some newer files (e.g., `mlflow_oidc_auth/entities/user.py`)
- Strict TypeScript (`strict: true` in tsconfig)
- Generic types used for HTTP: `async function http<T = unknown>(url: string, ...): Promise<T>`
- Vitest `Mock` type for typed test mocks: `const mockUseAuthErrors: Mock<() => string[]> = vi.fn()`
- React component props typed inline or via type parameters
## Documentation Patterns
- Every module starts with a triple-quoted docstring describing purpose:
- Use Google/Sphinx hybrid style with `Parameters`, `Returns`, `Raises`:
- Inline comments for important logic or TODO items
- Test classes have docstrings describing the test group
- Individual test methods have one-line docstrings describing the scenario:
- No JSDoc/TSDoc convention enforced
- Minimal inline comments
## Git Conventions
- **Conventional Commits** required, enforced by CI
- Pattern: `^(feat|fix|chore|docs|style|ci|refactor|perf|test|build)(\([\w-]+\))?:\s.+$`
- Types: `feat`, `fix`, `chore`, `docs`, `style`, `ci`, `refactor`, `perf`, `test`, `build`
- Must follow Conventional Commits format (enforced by `.github/workflows/pr-validate-title.yml`)
- Subject must NOT start with uppercase letter
- Scope is optional: `feat(auth): add token refresh`
- `main` - production releases
- `rc` - release candidate (pre-release channel)
- Semantic release via `.releaserc` with `@semantic-release/commit-analyzer`
- Automated via semantic-release on push to `main`
- Builds Python wheel and publishes to PyPI
- Uses `@semantic-release/exec` with `scripts/release.sh` for version bumping
- React UI is built during release (`vite build` outputs to `mlflow_oidc_auth/ui/`)
## Logging
- Singleton logger: `logger = get_logger()` at module level
- Logger defaults to `uvicorn` logger name (for FastAPI compatibility)
- Log level configurable via `LOG_LEVEL` environment variable
- Format: `%(asctime)s %(levelname)s %(name)s: %(message)s`
- Use `logger.info()`, `logger.warning()`, `logger.error()` for operational messages
## Module Design
- All packages use `__init__.py` with explicit `__all__` lists
- Re-export key symbols from submodules for convenient importing
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
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## Pattern Overview
- FastAPI (ASGI) handles authentication, OIDC flows, permission management API, and UI serving
- Flask (WSGI) handles core MLflow tracking API (experiments, runs, models, etc.) via MLflow's native app
- Flask app is mounted inside FastAPI via `AuthAwareWSGIMiddleware` (ASGI-to-WSGI bridge)
- Auth context flows from FastAPI middleware → ASGI scope → WSGI environ → Flask request.environ
- Plugin-based integration: installed as an MLflow app plugin via entry point `mlflow.app`
- Repository pattern for data access with SQLAlchemy ORM and Alembic migrations
- Chain-of-responsibility pattern for configuration providers (secrets managers, env vars)
## Layers
- Purpose: HTTP entry point, OIDC auth flows, permission management REST API, React SPA serving
- Location: `mlflow_oidc_auth/app.py`
- Contains: App factory (`create_app`), middleware stack setup, router registration, Flask app mounting
- Depends on: Routers, Middleware, Config, Store, OAuth
- Used by: ASGI server (uvicorn via MLflow CLI)
- Purpose: Authentication, proxy header handling, session management, WSGI bridging
- Location: `mlflow_oidc_auth/middleware/`
- Contains: `AuthMiddleware`, `AuthAwareWSGIMiddleware`, `ProxyHeadersMiddleware`
- Depends on: Config, Store, Auth (JWT validation), Bridge
- Used by: FastAPI app (applied in order during `create_app`)
- Purpose: REST API endpoints for permissions, users, groups, auth flows, health, UI
- Location: `mlflow_oidc_auth/routers/`
- Contains: 15 routers — auth, experiment_permissions, group_permissions, prompt_permissions, registered_model_permissions, scorers_permissions, gateway_endpoint_permissions, gateway_secret_permissions, gateway_model_definition_permissions, health, trash, ui, user_permissions, users, webhook
- Depends on: Store, Config, Models (Pydantic), Utils
- Used by: FastAPI app (registered in `create_app`)
- Purpose: RBAC enforcement on MLflow's native Flask endpoints
- Location: `mlflow_oidc_auth/hooks/`
- Contains: `before_request.py` (~428 lines) maps MLflow protobuf request classes to validator functions; `after_request.py` (~426 lines) handles post-request actions (auto-grant MANAGE on create, filter search results, cascade permission deletes)
- Depends on: Validators, Store, Bridge, Config, Permissions
- Used by: Flask app (registered as `before_request` and `after_request` hooks)
- Purpose: Per-resource permission checking logic
- Location: `mlflow_oidc_auth/validators/`
- Contains: Validator functions for experiments, registered models, prompts, scorers, gateway endpoints/secrets/model definitions
- Depends on: Store, Bridge, Permissions, Utils
- Used by: Hooks layer (before_request dispatches to validators)
- Purpose: Authorization middleware for MLflow's `/graphql` endpoint
- Location: `mlflow_oidc_auth/graphql/`
- Contains: Custom authorization middleware that intercepts GraphQL queries
- Depends on: Bridge, Store, Permissions
- Used by: Flask app (via MLflow's GraphQL integration)
- Purpose: Retrieves FastAPI auth context from Flask's WSGI environ
- Location: `mlflow_oidc_auth/bridge/`
- Key file: `mlflow_oidc_auth/bridge/user.py`
- Contains: `get_request_username()` extracts username from `request.environ["mlflow_oidc_auth"]`
- Depends on: Flask request context
- Used by: Hooks, Validators, GraphQL layer
- Purpose: All database operations for users, groups, permissions
- Location: `mlflow_oidc_auth/sqlalchemy_store.py` (main), `mlflow_oidc_auth/store.py` (singleton)
- Contains: `SqlAlchemyStore` class (~721 lines) delegates to 20+ repository classes
- Depends on: Repository classes, DB models, Entities, SQLAlchemy, Alembic
- Used by: Routers, Hooks, Validators, Middleware
- Purpose: Individual CRUD operations per entity type
- Location: `mlflow_oidc_auth/repository/`
- Contains: 20+ repository classes (UserRepository, GroupRepository, ExperimentPermissionRepository, RegisteredModelRegexPermissionRepository, etc.)
- Depends on: DB models, Entities, SQLAlchemy session
- Used by: SqlAlchemyStore
- Purpose: SQLAlchemy ORM table definitions
- Location: `mlflow_oidc_auth/db/models/`
- Contains: ORM models for all entities (users, groups, user_groups, experiment_permissions, registered_model_permissions, prompt_permissions, scorer_permissions, gateway_*_permissions, plus regex and group-regex variants of each)
- Depends on: SQLAlchemy declarative base
- Used by: Repository classes, Alembic migrations
- Purpose: Plain Python dataclasses representing domain objects (decoupled from ORM)
- Location: `mlflow_oidc_auth/entities/`
- Contains: Entity classes matching each DB model
- Depends on: Nothing (pure data classes)
- Used by: Store, Routers, Validators
- Purpose: Request/response validation for FastAPI endpoints
- Location: `mlflow_oidc_auth/models/`
- Contains: Pydantic BaseModel classes for API input/output
- Depends on: Pydantic
- Used by: Routers
- Purpose: Application configuration with pluggable secret providers
- Location: `mlflow_oidc_auth/config.py` (AppConfig), `mlflow_oidc_auth/config_providers/` (providers)
- Contains: `AppConfig` dataclass, `ConfigManager` singleton with chain-of-responsibility provider resolution
- Depends on: Config providers (AWS Secrets Manager, AWS Parameter Store, Azure Key Vault, HashiCorp Vault, Kubernetes Secrets, Environment Variables)
- Used by: All layers
- Purpose: Admin UI for managing permissions, users, groups
- Location: `web-react/`
- Contains: React 19 + TypeScript + Vite + TailwindCSS application
- Depends on: FastAPI REST API (via fetch with cookie-based sessions)
- Used by: End users via browser, served from `/oidc/ui/` by FastAPI `ui_router`
## Data Flow
- React Context for global state (auth status, config)
- React Query / SWR patterns via custom hooks in `core/hooks/`
- Runtime config loaded from `/oidc/ui/config.json` endpoint at startup
- Protected routes via `ProtectedRoute` component; admin routes for trash/webhooks
## Key Abstractions
- Purpose: Represents an access level for a resource
- Definition: `mlflow_oidc_auth/permissions.py`
- Values: `READ`, `USE`, `EDIT`, `MANAGE`, `NO_PERMISSIONS` (priority-ordered dataclass)
- Pattern: Comparable via priority field for permission level checks
- Purpose: Central data access facade — all DB operations go through this
- Definition: `mlflow_oidc_auth/sqlalchemy_store.py`
- Singleton: `mlflow_oidc_auth/store.py` (module-level `store` instance)
- Pattern: Facade over 20+ repository classes, each handling one entity type
- Purpose: Immutable application configuration
- Definition: `mlflow_oidc_auth/config.py`
- Pattern: Dataclass populated by `ConfigManager` from pluggable providers
- Purpose: Resolves configuration values from multiple secret backends
- Definition: `mlflow_oidc_auth/config_providers/manager.py`
- Pattern: Chain-of-responsibility — tries AWS Secrets Manager, AWS Parameter Store, Azure Key Vault, HashiCorp Vault, Kubernetes Secrets, then Environment Variables (fallback)
- Extensible: Custom providers via `mlflow_oidc_auth.config_provider` entry point
- Purpose: Bridges FastAPI (ASGI) to Flask (WSGI) while preserving auth context
- Definition: `mlflow_oidc_auth/middleware/auth_aware_wsgi_middleware.py`
- Pattern: Extends standard ASGI-to-WSGI middleware, copies `mlflow_oidc_auth` from ASGI scope to WSGI environ
- Purpose: Retrieves authenticated username inside Flask request context
- Definition: `mlflow_oidc_auth/bridge/user.py`
- Pattern: Reads from `flask.request.environ["mlflow_oidc_auth"]`
## Entry Points
- Location: `pyproject.toml` → `[project.entry-points."mlflow.app"]`
- Value: `oidc-auth = "mlflow_oidc_auth.app:app"`
- Triggers: `mlflow server --app-name oidc-auth`
- Responsibilities: MLflow loads `mlflow_oidc_auth.app:app` as the ASGI application
- Location: `mlflow_oidc_auth/cli.py`
- Command: `mlflow-oidc-server`
- Triggers: Installed as console script via pyproject.toml
- Responsibilities: Wraps `mlflow server --app-name oidc-auth` with additional CLI options
- Location: `mlflow_oidc_auth/app.py` → `create_app()`
- Triggers: Called when MLflow loads the plugin
- Responsibilities: Creates FastAPI app, configures middleware stack, registers all routers, creates MLflow Flask app, mounts Flask via `AuthAwareWSGIMiddleware`, runs DB migrations, creates default admin user
- Location: `web-react/src/main.tsx`
- Triggers: Browser loads `/oidc/ui/`
- Responsibilities: Renders React app with router, context providers
## Error Handling
- FastAPI exception handlers registered in `mlflow_oidc_auth/exceptions.py` for `HTTPException`, `MlflowException`, and generic `Exception`
- MLflow exceptions (e.g., `ResourceDoesNotExist`) are caught and mapped to appropriate HTTP status codes
- Hooks layer raises `HTTPException` (403/401) when permission checks fail
- Validators return boolean or raise exceptions on authorization failure
- Frontend handles HTTP errors in the shared HTTP client (`web-react/src/core/services/http.ts`)
## Cross-Cutting Concerns
- Custom logger setup in `mlflow_oidc_auth/logger.py`
- Used throughout backend via standard Python logging
- FastAPI Pydantic models for request/response validation on permission management API
- MLflow's own protobuf-based validation for core MLflow API endpoints
- Frontend form validation in React components
- Multi-method: OIDC, Basic Auth, Bearer Token (JWT), Session cookies
- `AuthMiddleware` handles all methods, sets unified auth context
- JWT validation via OIDC provider's JWKS endpoint (`mlflow_oidc_auth/auth.py`)
- OAuth client configured in `mlflow_oidc_auth/oauth.py` using authlib
- RBAC with configurable permission resolution order
- Permission types: user-level, group-level, regex (pattern-matched), group-regex
- Admin users bypass all checks
- Enforced in Flask hooks (before_request) for MLflow API
- Enforced in FastAPI route dependencies for permission management API
- GraphQL authorization middleware for `/graphql` endpoint
- Alembic manages schema migrations
- Migrations run automatically on app startup in `create_app()`
- Migration scripts in `mlflow_oidc_auth/db/migrations/versions/`
- `mlflow_oidc_auth/hack.py` injects navigation links into MLflow's built-in UI HTML
- Adds "Sign In" / "Sign Out" and permission management links to MLflow's navbar
<!-- GSD:architecture-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd:quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd:debug` for investigation and bug fixing
- `/gsd:execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd:profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
