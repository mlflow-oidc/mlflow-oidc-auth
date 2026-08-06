# Milestones

## v1.0 Workspace Support (Shipped: 2026-03-24)

**Phases completed:** 4 phases, 10 plans, 19 tasks

**Key accomplishments:**

- Registry-driven resolve_permission() consolidating 8 copy-paste source config functions and 10+ duplicate regex matchers into a single PERMISSION_REGISTRY with 7 resource type builders
- 4 generic base repository classes (BaseUserPermissionRepository, BaseGroupPermissionRepository, BaseRegexPermissionRepository, BaseGroupRegexPermissionRepository) eliminating ~1360 lines of duplicated CRUD across 28 permission repository subclasses
- Feature-flag-gated workspace plumbing: AuthContext frozen dataclass propagated through FastAPI→ASGI→WSGI→Flask bridge, workspace_permissions/workspace_group_permissions Alembic tables, X-MLFLOW-WORKSPACE header extraction, and default workspace startup seeding
- Standalone workspace permission repos, store facade methods, and TTLCache-backed cached lookups with implicit default workspace MANAGE access
- Workspace security boundary wired into permission resolution chain — validators, hook registration, resolve_permission() workspace fallback, CreateExperiment/Model MANAGE gating, and ListWorkspaces filtering
- Fixed _get_workspace_gated_creation_paths() filter from truthiness check to handler identity check, preventing /graphql, /server-info, and 15 other non-creation paths from being incorrectly workspace-gated
- 8-endpoint FastAPI CRUD router for workspace user+group permission management with Pydantic models, MANAGE/READ dependency checks, store group facade methods, and selective cache invalidation
- OIDC workspace claim mapping (plugin-first, JWT claim fallback, auto-assign) and PromptOptimizationJob auth coverage with 5 before_request handlers
- Complete workspace UI data pipeline from backend config.json through TypeScript types, API endpoints, service fetchers, data hooks, sidebar navigation, and route registration
- Workspace list page with search/filter and detail page with full CRUD member management (add/edit/remove users and groups with toast notifications)

### Known Gaps

- **ENTITY-02**: GatewayBudgetPolicy before_request handlers — deferred, protos not present in MLflow 3.10.1

---
