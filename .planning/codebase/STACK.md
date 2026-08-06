# Technology Stack

**Analysis Date:** 2026-03-23

## Languages

**Primary:**
- Python 3.12 - Backend server, auth plugin, CLI, database models, API routers (`.python-version`, CI uses `python-version: 3.12`)
- TypeScript ~5.9 - React frontend UI (`web-react/package.json`)

**Secondary:**
- SQL - Database migrations via Alembic (`mlflow_oidc_auth/db/migrations/`)
- Bash - Dev/release scripts (`scripts/release.sh`, `scripts/run-dev-server.sh`)
- YAML - CI/CD workflows, Docker Compose (`scripts/docker-compose.yaml`, `.github/workflows/`)

## Runtime

**Python Environment:**
- Python >=3.10 (declared in `pyproject.toml`), 3.12 used in development/CI
- Tox test matrix targets `py314` (`tox.ini` envlist)

**Node Environment:**
- Node 24 (CI uses `node-version: 24` in `.github/workflows/unit-tests.yml`)
- ES modules (`"type": "module"` in `web-react/package.json`)

**Package Managers:**
- pip + setuptools for Python (`pyproject.toml` build-system)
- Yarn for JavaScript (`web-react/yarn.lock` present)
- Lockfile: `web-react/yarn.lock` present; no Python lockfile (pip freeze / tox managed)

## Frameworks

**Core:**
- FastAPI >=0.132.0 - Primary ASGI application framework (`pyproject.toml`, `mlflow_oidc_auth/app.py`)
- Flask <4 - MLflow's built-in web framework, mounted as WSGI under FastAPI (`mlflow_oidc_auth/app.py`)
- Starlette - Underlying ASGI framework (via FastAPI), session middleware (`starlette.middleware.sessions`)
- MLflow >=3.10.0, <4 - ML experiment tracking server; this project is an auth plugin (`pyproject.toml`)

**Frontend:**
- React 19.1 - UI framework (`web-react/package.json`)
- React Router 7.9 - Client-side routing (`web-react/package.json`)
- Tailwind CSS 4 - Utility-first CSS framework (`@tailwindcss/vite` plugin in `web-react/package.json`)
- FontAwesome 7 - Icon library (`@fortawesome/*` packages)

**Testing:**
- pytest >=8.3.2 - Python test runner (`pyproject.toml`)
- pytest-asyncio <2 - Async test support, mode `auto` (`pyproject.toml`)
- pytest-cov >=5.0.0 - Coverage reporting (`pyproject.toml`)
- Vitest 4.0 - JavaScript test runner (`web-react/package.json`)
- Testing Library (React 16, DOM 10, jest-dom 6, user-event 14) - React component testing
- jsdom 27 - Browser environment for Vitest (`web-react/vite.config.ts`)
- Playwright - Integration/E2E browser tests (`tox.ini` integration env)

**Build/Dev:**
- Vite (rolldown-vite 7.3.1) - Frontend build tool, aliased via `npm:rolldown-vite@7.3.1` (`web-react/package.json`)
- SWC - Fast React compilation via `@vitejs/plugin-react-swc` (`web-react/vite.config.ts`)
- setuptools - Python build backend (`pyproject.toml`)
- tox - Test environment management (`tox.ini`)
- pre-commit - Git hooks for code quality (`.pre-commit-config.yaml`)
- semantic-release - Automated versioning and release (`.releaserc`)

## Key Dependencies

**Critical Runtime (Python):**
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

**Critical Runtime (Frontend):**
- `react` 19.1 / `react-dom` 19.1 - UI rendering
- `react-router` 7.9 - Client-side routing (devDependency in package.json but used at runtime)
- `dompurify` 3.3 - HTML sanitization
- `@fortawesome/*` 7.1 / 3.1 - Icon components

**Optional Cloud Provider Dependencies:**
- `boto3` >=1.42.26 - AWS Secrets Manager + Parameter Store (`pyproject.toml` `[aws]` extra)
- `azure-identity` >=1.25.1, `azure-keyvault-secrets` >=4.10.0 - Azure Key Vault (`pyproject.toml` `[azure]` extra)
- `hvac` >=2.4.0 - HashiCorp Vault client (`pyproject.toml` `[vault]` extra)

**Dev/Test (Python):**
- `black` >=24.8.0, <26 - Code formatter (`pyproject.toml` `[dev]` extra, `.pre-commit-config.yaml`)
- `autoflake` <2 - Unused import removal (`pyproject.toml` `[dev]` extra)
- `pre-commit` <5 - Git hook manager
- `coverage` <=7.6 - Code coverage (`tox.ini`)
- `bandit` - Security linter (`.github/workflows/bandit.yml`)

**Dev/Test (Frontend):**
- `typescript` ~5.9 - Type checking
- `eslint` ~9.36 + plugins - Linting (`web-react/eslint.config.js`)
- `prettier` ~3.8 - Code formatting (`web-react/.prettierrc`)
- `@vitest/coverage-v8` 4.0 - Coverage reporting

## Database / Storage

**Auth Database:**
- SQLAlchemy 2.x ORM with Alembic migrations (`mlflow_oidc_auth/db/`)
- Default: SQLite (`sqlite:///auth.db` per `mlflow_oidc_auth/config.py`)
- Supported: PostgreSQL, MySQL, any SQLAlchemy-compatible database
- Connection URI configured via `OIDC_USERS_DB_URI` environment variable
- Schema managed via Alembic migrations in `mlflow_oidc_auth/db/migrations/versions/`
- SQLAlchemy `DeclarativeBase` used (`mlflow_oidc_auth/db/models/_base.py`)
- Helper scripts for PostgreSQL (`scripts/postgresql/`) and MySQL (`scripts/mysql/`)

**MLflow Backend Store:**
- Managed separately by MLflow (not by this plugin)
- Configured via `MLFLOW_BACKEND_STORE_URI` environment variable

**Session Storage:**
- Cookie-based sessions via Starlette `SessionMiddleware` (no server-side session store)
- Signed with `SECRET_KEY` configuration value
- All replicas must share the same `SECRET_KEY` for multi-instance deployments

**Testing Support:**
- Redis available via Docker Compose for cache integration testing (`scripts/docker-compose.yaml`)

## Configuration

**Environment:**
- Primary: Environment variables (with `python-dotenv` `.env` file loading)
- Pluggable config provider chain: AWS Secrets Manager → Azure Key Vault → HashiCorp Vault → Kubernetes Secrets → AWS Parameter Store → Environment Variables (`mlflow_oidc_auth/config_providers/manager.py`)
- `AppConfig` singleton in `mlflow_oidc_auth/config.py` loads all configuration

**Key Config Files:**
- `pyproject.toml` - Python package metadata, build config, tool settings
- `web-react/package.json` - Frontend dependencies and scripts
- `tox.ini` - Test environment configuration
- `.pre-commit-config.yaml` - Pre-commit hook configuration
- `.releaserc` - Semantic release configuration
- `.editorconfig` - Editor formatting settings
- `sonar-project.properties` - SonarCloud configuration
- `.coveragerc` - Python coverage configuration

**Build Configuration:**
- `web-react/vite.config.ts` - Vite build config, outputs to `../mlflow_oidc_auth/ui`
- `web-react/tsconfig.json` + `tsconfig.app.json` + `tsconfig.node.json` - TypeScript config
- `web-react/eslint.config.js` - ESLint flat config

## Platform Requirements

**Development:**
- Python 3.12 (via `.python-version`)
- Node.js 24 (per CI config)
- Yarn package manager
- Optional: Docker Compose for Redis testing

**Production:**
- Python >=3.10 (>=3.12 recommended)
- No Node.js required (frontend is pre-built into `mlflow_oidc_auth/ui/`)
- ASGI server: uvicorn (bundled dependency)
- Database: SQLite (default) or PostgreSQL/MySQL

**Deployment:**
- PyPI package: `pip install mlflow-oidc-auth`
- Optional extras: `pip install mlflow-oidc-auth[aws]`, `[azure]`, `[vault]`, `[cloud]`
- CLI entry point: `mlflow-oidc-server` (installed via `[project.scripts]`)
- MLflow plugin entry point: `mlflow server --app-name oidc-auth` (via `[project.entry-points."mlflow.app"]`)

---

*Stack analysis: 2026-03-23*
