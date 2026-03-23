# Codebase Structure

**Analysis Date:** 2026-03-23

## Directory Layout

```
mlflow-oidc-auth/
├── mlflow_oidc_auth/              # Backend Python package (FastAPI + Flask plugin)
│   ├── __init__.py                # Package init, version
│   ├── app.py                     # FastAPI app factory (create_app)
│   ├── cli.py                     # CLI entry point (mlflow-oidc-server)
│   ├── config.py                  # AppConfig dataclass
│   ├── auth.py                    # JWT token validation
│   ├── oauth.py                   # OIDC/OAuth client setup (authlib)
│   ├── user.py                    # User create/update helpers
│   ├── permissions.py             # Permission dataclass (READ/USE/EDIT/MANAGE)
│   ├── store.py                   # SqlAlchemyStore singleton instance
│   ├── sqlalchemy_store.py        # Full store implementation (~721 lines)
│   ├── exceptions.py              # FastAPI exception handlers
│   ├── logger.py                  # Logging setup
│   ├── hack.py                    # MLflow UI menu injection
│   ├── bridge/                    # FastAPI↔Flask auth context bridge
│   │   └── user.py                # get_request_username()
│   ├── config_providers/          # Pluggable config provider system
│   │   ├── manager.py             # ConfigManager (chain-of-responsibility)
│   │   ├── aws_secrets_manager.py
│   │   ├── aws_parameter_store.py
│   │   ├── azure_key_vault.py
│   │   ├── hashicorp_vault.py
│   │   ├── kubernetes.py
│   │   └── env.py                 # Environment variables (fallback)
│   ├── db/                        # Database layer
│   │   ├── models/                # SQLAlchemy ORM models
│   │   │   ├── base.py            # Declarative base
│   │   │   ├── user.py
│   │   │   ├── group.py
│   │   │   ├── user_group.py
│   │   │   ├── experiment_permission.py
│   │   │   ├── experiment_group_permission.py
│   │   │   ├── experiment_regex_permission.py
│   │   │   ├── experiment_group_regex_permission.py
│   │   │   ├── registered_model_permission.py
│   │   │   ├── registered_model_group_permission.py
│   │   │   ├── registered_model_regex_permission.py
│   │   │   ├── registered_model_group_regex_permission.py
│   │   │   ├── prompt_permission.py
│   │   │   ├── prompt_group_permission.py
│   │   │   ├── prompt_regex_permission.py
│   │   │   ├── prompt_group_regex_permission.py
│   │   │   ├── scorer_permission.py
│   │   │   ├── scorer_group_permission.py
│   │   │   ├── scorer_regex_permission.py
│   │   │   ├── scorer_group_regex_permission.py
│   │   │   ├── gateway_endpoint_permission.py
│   │   │   ├── gateway_endpoint_group_permission.py
│   │   │   ├── gateway_endpoint_regex_permission.py
│   │   │   ├── gateway_endpoint_group_regex_permission.py
│   │   │   ├── gateway_secret_permission.py
│   │   │   ├── gateway_secret_group_permission.py
│   │   │   ├── gateway_secret_regex_permission.py
│   │   │   ├── gateway_secret_group_regex_permission.py
│   │   │   ├── gateway_model_definition_permission.py
│   │   │   ├── gateway_model_definition_group_permission.py
│   │   │   ├── gateway_model_definition_regex_permission.py
│   │   │   └── gateway_model_definition_group_regex_permission.py
│   │   └── migrations/            # Alembic migrations
│   │       ├── alembic.ini
│   │       ├── env.py
│   │       ├── script.py.mako
│   │       └── versions/          # Migration scripts
│   ├── entities/                   # Domain entity dataclasses
│   │   ├── user.py
│   │   ├── group.py
│   │   ├── user_group.py
│   │   ├── experiment_permission.py
│   │   ├── registered_model_permission.py
│   │   ├── prompt_permission.py
│   │   ├── scorer_permission.py
│   │   ├── gateway_endpoint_permission.py
│   │   ├── gateway_secret_permission.py
│   │   └── gateway_model_definition_permission.py
│   ├── graphql/                    # GraphQL authorization
│   │   └── middleware.py           # Authorization middleware for /graphql
│   ├── hooks/                      # Flask before/after request hooks
│   │   ├── __init__.py
│   │   ├── before_request.py       # RBAC enforcement (~428 lines)
│   │   └── after_request.py        # Post-request actions (~426 lines)
│   ├── middleware/                  # ASGI middleware
│   │   ├── __init__.py
│   │   ├── auth_middleware.py      # Authentication (Basic/Bearer/Session)
│   │   ├── auth_aware_wsgi_middleware.py  # ASGI→WSGI bridge with auth context
│   │   └── proxy_headers_middleware.py    # X-Forwarded-* header handling
│   ├── models/                     # Pydantic request/response models
│   │   ├── experiment_permission.py
│   │   ├── registered_model_permission.py
│   │   ├── prompt_permission.py
│   │   ├── scorer_permission.py
│   │   ├── gateway_endpoint_permission.py
│   │   ├── gateway_secret_permission.py
│   │   ├── gateway_model_definition_permission.py
│   │   ├── group.py
│   │   ├── user.py
│   │   └── auth.py
│   ├── repository/                 # Data access repositories
│   │   ├── user.py
│   │   ├── group.py
│   │   ├── user_group.py
│   │   ├── experiment_permission.py
│   │   ├── experiment_group_permission.py
│   │   ├── experiment_regex_permission.py
│   │   ├── experiment_group_regex_permission.py
│   │   ├── registered_model_permission.py
│   │   ├── registered_model_group_permission.py
│   │   ├── registered_model_regex_permission.py
│   │   ├── registered_model_group_regex_permission.py
│   │   ├── prompt_permission.py
│   │   ├── prompt_group_permission.py
│   │   ├── prompt_regex_permission.py
│   │   ├── prompt_group_regex_permission.py
│   │   ├── scorer_permission.py
│   │   ├── scorer_group_permission.py
│   │   ├── scorer_regex_permission.py
│   │   ├── scorer_group_regex_permission.py
│   │   ├── gateway_endpoint_permission.py
│   │   ├── gateway_endpoint_group_permission.py
│   │   ├── gateway_endpoint_regex_permission.py
│   │   ├── gateway_endpoint_group_regex_permission.py
│   │   ├── gateway_secret_permission.py
│   │   ├── gateway_secret_group_permission.py
│   │   ├── gateway_secret_regex_permission.py
│   │   ├── gateway_secret_group_regex_permission.py
│   │   ├── gateway_model_definition_permission.py
│   │   ├── gateway_model_definition_group_permission.py
│   │   ├── gateway_model_definition_regex_permission.py
│   │   └── gateway_model_definition_group_regex_permission.py
│   ├── routers/                    # FastAPI route handlers
│   │   ├── __init__.py             # Router registration list
│   │   ├── _prefix.py             # URL prefix constants
│   │   ├── auth.py                # Login/logout/callback/auth-status
│   │   ├── experiment_permissions.py
│   │   ├── group_permissions.py
│   │   ├── prompt_permissions.py
│   │   ├── registered_model_permissions.py
│   │   ├── scorers_permissions.py
│   │   ├── gateway_endpoint_permissions.py
│   │   ├── gateway_secret_permissions.py
│   │   ├── gateway_model_definition_permissions.py
│   │   ├── health.py
│   │   ├── trash.py
│   │   ├── ui.py                  # SPA serving & config endpoint
│   │   ├── user_permissions.py
│   │   ├── users.py
│   │   └── webhook.py
│   ├── utils/                      # Utility modules
│   │   ├── permissions.py         # Permission resolution helpers
│   │   ├── data_fetching.py       # Data fetch utilities
│   │   ├── request_helpers.py     # Request parsing helpers
│   │   └── uri.py                 # URI manipulation
│   └── validators/                 # Permission validator functions
│       ├── experiment.py
│       ├── registered_model.py
│       ├── prompt.py
│       ├── scorer.py
│       ├── gateway_endpoint.py
│       ├── gateway_secret.py
│       └── gateway_model_definition.py
├── web-react/                      # Frontend React SPA
│   ├── package.json
│   ├── tsconfig.json
│   ├── tsconfig.app.json
│   ├── tsconfig.node.json
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   ├── postcss.config.mjs
│   ├── index.html
│   ├── public/                     # Static assets
│   └── src/
│       ├── main.tsx                # React entry point
│       ├── app.tsx                 # Route definitions (~390 lines)
│       ├── index.css               # Global styles
│       ├── core/                   # Core application infrastructure
│       │   ├── components/         # Layout components (ProtectedRoute, etc.)
│       │   ├── configs/            # Configuration
│       │   │   └── api-endpoints.ts  # All API endpoint definitions
│       │   ├── context/            # React contexts (auth, config)
│       │   ├── hooks/              # Custom hooks for data fetching
│       │   ├── services/           # HTTP client and API services
│       │   │   └── http.ts         # Fetch-based HTTP client
│       │   └── types/              # Core TypeScript types
│       ├── features/               # Feature modules (14 features)
│       │   ├── auth/               # Authentication UI
│       │   ├── experiments/        # Experiment permission management
│       │   ├── models/             # Registered model permission management
│       │   ├── groups/             # Group management
│       │   ├── prompts/            # Prompt permission management
│       │   ├── ai-gateway/         # AI Gateway permission management
│       │   ├── users/              # User management
│       │   ├── service-accounts/   # Service account management
│       │   ├── trash/              # Soft-deleted resource management
│       │   ├── webhooks/           # Webhook management
│       │   ├── permissions/        # Permission views
│       │   ├── forbidden/          # 403 page
│       │   ├── not-found/          # 404 page
│       │   └── user/               # User profile/settings
│       └── shared/                 # Shared components and utilities
│           ├── components/         # Reusable UI components
│           ├── context/            # Shared React contexts
│           ├── services/           # Shared service utilities
│           ├── types/              # Shared TypeScript types
│           └── utils/              # Shared utility functions
├── tests/                          # Backend test suite
│   ├── conftest.py
│   └── ...                         # Test files
├── scripts/                        # Development and deployment scripts
│   ├── dev-server.sh
│   └── ...
├── pyproject.toml                  # Python package config, dependencies, entry points
├── Makefile                        # Build/dev commands
├── Dockerfile                      # Container build
├── docker-compose.yml              # Local dev environment
├── .github/                        # GitHub Actions CI/CD workflows
└── .planning/                      # GSD planning documents
```

## Directory Purposes

**`mlflow_oidc_auth/`:**
- Purpose: Main Python package — the MLflow auth plugin
- Contains: FastAPI app, middleware, routers, hooks, validators, store, DB models, entities, repositories, config providers, utilities
- Key files: `app.py` (entry point), `sqlalchemy_store.py` (data access), `config.py` (configuration)

**`mlflow_oidc_auth/routers/`:**
- Purpose: FastAPI route handlers for the permission management REST API
- Contains: One router per resource type, plus auth, health, UI, users, trash, webhook routers
- Key files: `__init__.py` (router list), `_prefix.py` (URL prefixes), `auth.py` (OIDC flows)

**`mlflow_oidc_auth/hooks/`:**
- Purpose: Flask before/after request hooks that enforce RBAC on MLflow's native API
- Contains: `before_request.py` (permission checks), `after_request.py` (auto-grant, filtering, cascading)
- Key files: `before_request.py` (~428 lines, maps protobuf classes to validators)

**`mlflow_oidc_auth/middleware/`:**
- Purpose: ASGI middleware stack for authentication, proxy handling, WSGI bridging
- Contains: `auth_middleware.py`, `auth_aware_wsgi_middleware.py`, `proxy_headers_middleware.py`
- Key files: `auth_middleware.py` (multi-method auth), `auth_aware_wsgi_middleware.py` (ASGI↔WSGI bridge)

**`mlflow_oidc_auth/validators/`:**
- Purpose: Per-resource permission validation logic
- Contains: One validator module per resource type (experiment, registered_model, prompt, scorer, gateway_*)
- Key files: `experiment.py`, `registered_model.py`

**`mlflow_oidc_auth/db/models/`:**
- Purpose: SQLAlchemy ORM table definitions
- Contains: One model file per table (4 variants per resource: user, group, regex, group-regex)
- Key files: `base.py` (declarative base), `user.py`, `group.py`

**`mlflow_oidc_auth/db/migrations/`:**
- Purpose: Alembic database migration scripts
- Contains: `alembic.ini`, `env.py`, migration versions
- Key files: `versions/` directory with timestamped migration scripts

**`mlflow_oidc_auth/entities/`:**
- Purpose: Domain entity dataclasses (decoupled from ORM)
- Contains: One entity file per domain concept
- Key files: `user.py`, `group.py`, `experiment_permission.py`

**`mlflow_oidc_auth/repository/`:**
- Purpose: CRUD data access classes, one per entity type
- Contains: 28+ repository files (4 variants per resource type)
- Key files: `user.py`, `group.py`, `experiment_permission.py`

**`mlflow_oidc_auth/models/`:**
- Purpose: Pydantic request/response models for FastAPI endpoints
- Contains: Pydantic BaseModel classes for API validation
- Key files: `user.py`, `group.py`, `auth.py`

**`mlflow_oidc_auth/config_providers/`:**
- Purpose: Pluggable configuration providers for secrets/settings
- Contains: Provider implementations and manager
- Key files: `manager.py` (ConfigManager singleton)

**`mlflow_oidc_auth/bridge/`:**
- Purpose: Bridge between FastAPI (ASGI) and Flask (WSGI) auth contexts
- Contains: `user.py` with `get_request_username()`
- Key files: `user.py`

**`mlflow_oidc_auth/graphql/`:**
- Purpose: Authorization middleware for MLflow's GraphQL endpoint
- Contains: GraphQL authorization logic
- Key files: `middleware.py`

**`mlflow_oidc_auth/utils/`:**
- Purpose: Shared utility functions
- Contains: Permission resolution, data fetching, request parsing, URI helpers
- Key files: `permissions.py` (permission resolution logic)

**`web-react/src/core/`:**
- Purpose: Core frontend infrastructure — hooks, services, configs, contexts, types
- Contains: Shared application-level code used by all features
- Key files: `services/http.ts` (HTTP client), `configs/api-endpoints.ts` (all endpoints)

**`web-react/src/features/`:**
- Purpose: Feature-based modules — each feature is self-contained with components, hooks, services
- Contains: 14 feature directories
- Key files: Each feature typically has `index.tsx`, `components/`, and feature-specific hooks

**`web-react/src/shared/`:**
- Purpose: Shared UI components and utilities used across features
- Contains: Reusable components, contexts, services, types, utils
- Key files: Shared table components, form components, utility functions

## Key File Locations

**Entry Points:**
- `mlflow_oidc_auth/app.py`: FastAPI app factory (`create_app`), the main plugin entry point
- `mlflow_oidc_auth/cli.py`: CLI command `mlflow-oidc-server`
- `web-react/src/main.tsx`: React SPA entry point
- `web-react/src/app.tsx`: React route definitions

**Configuration:**
- `pyproject.toml`: Python package metadata, dependencies, entry points, build config
- `mlflow_oidc_auth/config.py`: AppConfig dataclass
- `mlflow_oidc_auth/config_providers/manager.py`: ConfigManager
- `web-react/vite.config.ts`: Vite build configuration
- `web-react/tsconfig.json`: TypeScript configuration
- `web-react/tailwind.config.ts`: TailwindCSS configuration
- `mlflow_oidc_auth/db/migrations/alembic.ini`: Alembic migration config

**Core Logic:**
- `mlflow_oidc_auth/sqlalchemy_store.py`: All database operations (~721 lines)
- `mlflow_oidc_auth/hooks/before_request.py`: RBAC enforcement (~428 lines)
- `mlflow_oidc_auth/hooks/after_request.py`: Post-request actions (~426 lines)
- `mlflow_oidc_auth/middleware/auth_middleware.py`: Multi-method authentication
- `mlflow_oidc_auth/middleware/auth_aware_wsgi_middleware.py`: ASGI↔WSGI bridge
- `mlflow_oidc_auth/permissions.py`: Permission model
- `mlflow_oidc_auth/utils/permissions.py`: Permission resolution logic

**Testing:**
- `tests/`: Backend test suite
- `tests/conftest.py`: Test fixtures and configuration

## Naming Conventions

**Files (Python):**
- `snake_case.py` for all Python modules: `experiment_permission.py`, `before_request.py`
- Private/internal modules prefixed with underscore: `_prefix.py`

**Files (TypeScript/React):**
- `kebab-case.ts` / `kebab-case.tsx` for all frontend files: `api-endpoints.ts`, `http.ts`
- Feature directories use kebab-case: `ai-gateway/`, `service-accounts/`

**Directories:**
- `snake_case` for Python: `config_providers/`, `db/models/`
- `kebab-case` for TypeScript: `ai-gateway/`, `not-found/`

**Resource Permission Pattern:**
- Each resource type has 4 variants across models, repositories, and DB models:
  - `{resource}_permission` (user-level)
  - `{resource}_group_permission` (group-level)
  - `{resource}_regex_permission` (regex/pattern user-level)
  - `{resource}_group_regex_permission` (regex/pattern group-level)

## Where to Add New Code

**New Resource Type with Permissions:**
1. DB model (4 files): `mlflow_oidc_auth/db/models/{resource}_permission.py` (+ group, regex, group_regex variants)
2. Entity: `mlflow_oidc_auth/entities/{resource}_permission.py`
3. Repository (4 files): `mlflow_oidc_auth/repository/{resource}_permission.py` (+ variants)
4. Pydantic model: `mlflow_oidc_auth/models/{resource}_permission.py`
5. Store methods: Add to `mlflow_oidc_auth/sqlalchemy_store.py`
6. Validator: `mlflow_oidc_auth/validators/{resource}.py`
7. Router: `mlflow_oidc_auth/routers/{resource}_permissions.py`
8. Register router in `mlflow_oidc_auth/routers/__init__.py`
9. Add hooks in `mlflow_oidc_auth/hooks/before_request.py` and `after_request.py`
10. Alembic migration: `mlflow_oidc_auth/db/migrations/versions/`
11. Frontend feature: `web-react/src/features/{resource}/`
12. API endpoints: Add to `web-react/src/core/configs/api-endpoints.ts`
13. Routes: Add to `web-react/src/app.tsx`

**New FastAPI Router:**
1. Create router file: `mlflow_oidc_auth/routers/{name}.py`
2. Register in `mlflow_oidc_auth/routers/__init__.py`
3. Add URL prefix in `mlflow_oidc_auth/routers/_prefix.py` if needed

**New Config Provider:**
1. Create provider: `mlflow_oidc_auth/config_providers/{provider_name}.py`
2. Implement the provider interface (see existing providers for pattern)
3. Register in `ConfigManager` or via `mlflow_oidc_auth.config_provider` entry point

**New Frontend Feature:**
1. Create feature directory: `web-react/src/features/{feature-name}/`
2. Add components, hooks, services within the feature directory
3. Add routes in `web-react/src/app.tsx`
4. Add API endpoints in `web-react/src/core/configs/api-endpoints.ts`

**New Utility Function:**
- Backend: `mlflow_oidc_auth/utils/{module}.py`
- Frontend shared: `web-react/src/shared/utils/`
- Frontend core: `web-react/src/core/services/` or `web-react/src/core/hooks/`

**New Alembic Migration:**
- Generate: `alembic revision --autogenerate -m "description"`
- Location: `mlflow_oidc_auth/db/migrations/versions/`

## Special Directories

**`mlflow_oidc_auth/db/migrations/`:**
- Purpose: Alembic database schema migrations
- Generated: Migration scripts auto-generated, then manually reviewed
- Committed: Yes

**`web-react/node_modules/`:**
- Purpose: Frontend npm dependencies
- Generated: Yes (via `npm install`)
- Committed: No (in .gitignore)

**`web-react/dist/`:**
- Purpose: Built frontend assets (output of `vite build`)
- Generated: Yes
- Committed: No (in .gitignore)

**`.planning/`:**
- Purpose: GSD planning and analysis documents
- Generated: By GSD tooling
- Committed: Yes

**`.github/`:**
- Purpose: GitHub Actions CI/CD workflow definitions
- Generated: No (manually maintained)
- Committed: Yes

---

*Structure analysis: 2026-03-23*
