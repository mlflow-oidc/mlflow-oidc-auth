# Integration Test Findings & Application Improvements

This document captures potential improvements for the MLflow OIDC Auth Plugin based on integration test observations and API response analysis.

---

## 1. API Response Consistency

### 1.1 Inconsistent Denial Status Codes
**Issue:** Access denial returns different HTTP status codes across endpoints.

| Scenario | Current Behavior | Suggested |
|----------|------------------|-----------|
| Permission denied | 401, 403, 404, or 405 | Standardize to 403 for permission denial |
| Resource not found | Sometimes 404, sometimes 403 | Use 404 for missing resources, 403 for permission issues |
| Unauthenticated | 302 (redirect) or 401 | Use 401 with `WWW-Authenticate` header for API calls |
| Method not allowed | 405 | Keep 405 but document which methods require which permissions |

**Affected Endpoints:**
```
# Returns 405 for permission denial (should be 403):
PATCH ajax-api/2.0/mlflow/experiments/update

# Returns 302 redirect when Basic auth fails (should be 401):
POST ajax-api/2.0/mlflow/experiments/search
GET  ajax-api/2.0/mlflow/experiments/get-by-name

# Inconsistent denial codes across permission checks:
GET  ajax-api/2.0/mlflow/registered-models/get?name={name}
POST ajax-api/2.0/mlflow/runs/create
```

**Action Items:**
- [ ] Create middleware to normalize denial responses for API endpoints (non-browser)
- [ ] Return 401 (not 302) when Basic auth fails on `/api/` and `/ajax-api/` routes
- [ ] Add `WWW-Authenticate: Basic realm="MLflow"` header for 401 responses
- [ ] Return structured JSON error body with `error_code` and `message` fields

### 1.2 Experiment ID Field Naming
**Issue:** API responses use inconsistent field names for experiment ID.

```python
# Tests have to check multiple field names:
exp_id = exp.get("experiment_id") or exp.get("experimentId") or exp.get("id")
```

**Affected Endpoints:**
```
GET ajax-api/2.0/mlflow/experiments/get-by-name?experiment_name={name}
# Response varies: {"experiment": {"experiment_id": "..."}} vs {"experimentId": "..."}

GET ajax-api/2.0/mlflow/experiments/get?experiment_id={id}
POST ajax-api/2.0/mlflow/experiments/create
# Response: {"experiment_id": "..."} - correct format
```

**Action Items:**
- [ ] Standardize on `experiment_id` (snake_case) across all endpoints
- [ ] Add response transformation layer to ensure consistency
- [ ] Document the canonical field names in API documentation

### 1.3 Permission Create vs Update (POST vs PATCH)
**Issue:** Tests must try PATCH, then POST (or vice versa) when setting permissions.

```python
# Current workaround in tests:
resp = client.patch(api, json={"permission": permission})
if resp.status_code == 404:
    resp = client.post(api, json={"permission": permission})
```

**Affected Endpoints:**
```
# User permissions:
POST/PATCH api/2.0/mlflow/permissions/users/{username}/experiments/{experiment_id}
POST/PATCH api/2.0/mlflow/permissions/users/{username}/registered-models/{model_name}

# Group permissions:
POST/PATCH api/2.0/mlflow/permissions/groups/{group_name}/experiments/{experiment_id}
POST/PATCH api/2.0/mlflow/permissions/groups/{group_name}/registered-models/{model_name}
```

**Action Items:**
- [ ] Implement PUT endpoint that does "create or update" (upsert)
- [ ] Return 409 Conflict when POSTing an already-existing permission
- [ ] Return 404 when PATCHing non-existent permission
- [ ] Document the idempotent behavior of each HTTP method

---

## 2. Error Response Improvements

### 2.1 Structured Error Responses
**Issue:** Error responses lack consistent structure and machine-readable codes.

**Current:** Varies by endpoint, sometimes plain text, sometimes JSON.

**Suggested Format:**
```json
{
  "error_code": "PERMISSION_DENIED",
  "message": "User lacks MANAGE permission on experiment 123",
  "details": {
    "resource_type": "experiment",
    "resource_id": "123",
    "required_permission": "MANAGE",
    "user_permission": "READ"
  }
}
```

**Action Items:**
- [ ] Define error code enum (PERMISSION_DENIED, RESOURCE_NOT_FOUND, USER_NOT_FOUND, etc.)
- [ ] Create error response schema/model
- [ ] Update all permission enforcement to use structured errors
- [ ] Include helpful details like required vs actual permission level

### 2.2 Group Permission Deletion Error
**Issue:** Server returns 500 when deleting non-existent group permission.

```python
# From utils.py:
# Note: Server returns 500 when permission doesn't exist, not 404
httpx.request(method="DELETE", url=api_url, ...)
```

**Affected Endpoints:**
```
DELETE api/2.0/mlflow/permissions/groups/{group_name}/experiments/{experiment_id}
# Returns 500 Internal Server Error when permission doesn't exist

DELETE api/2.0/mlflow/permissions/groups/{group_name}/registered-models/{model_name}
# Same issue - returns 500 instead of 404
```

**Action Items:**
- [ ] Return 404 for DELETE on non-existent permission (idempotent)
- [ ] Alternatively, return 204 No Content (successful no-op)
- [ ] Never return 500 for expected conditions

---

## 3. Authentication Improvements

### 3.1 Bearer Token Authentication
**Issue:** `MLFLOW_TRACKING_TOKEN` (Bearer) doesn't work; must use Basic auth.

**Current Behavior:**
- MLflow SDK sets `MLFLOW_TRACKING_TOKEN` expecting Bearer auth
- Server only accepts Basic auth with username:token

**Affected Endpoints (all API endpoints):**
```
# These endpoints should accept Bearer token but currently don't:
Authorization: Bearer <token>

# All MLflow API endpoints:
GET/POST ajax-api/2.0/mlflow/experiments/*
GET/POST ajax-api/2.0/mlflow/runs/*
GET/POST ajax-api/2.0/mlflow/registered-models/*
GET/POST ajax-api/2.0/mlflow/model-versions/*

# Permission API endpoints:
GET/POST/PATCH/DELETE api/2.0/mlflow/permissions/*
GET/POST api/2.0/mlflow/users/*
```

**Action Items:**
- [ ] Support Bearer token authentication for API endpoints
- [ ] Parse `Authorization: Bearer <token>` header
- [ ] Look up user from token and authenticate
- [ ] Maintain Basic auth compatibility for backward compatibility
- [ ] Document both authentication methods

### 3.2 Token Response After Regeneration
**Issue:** Old token returns 302 (redirect) instead of 401 when invalid.

**Affected Endpoints:**
```
# Token regeneration endpoint:
PATCH api/2.0/mlflow/users/access-token
# Request: {"username": "user@example.com"}
# Response: {"token": "new-token-value"}

# After regeneration, old token causes 302 on:
POST ajax-api/2.0/mlflow/experiments/search
# Should return 401 with JSON error, not 302 redirect
```

**Action Items:**
- [ ] Return 401 with JSON body for invalid tokens on API endpoints
- [ ] Include `error_code: "INVALID_TOKEN"` or `"TOKEN_EXPIRED"`

---

## 4. Model Version Source Validation

### 4.1 Clearer Source Validation Error
**Issue:** Model version creation fails with vague error for invalid source.

**Current:** Returns 400 Bad Request with unclear message.

**Affected Endpoint:**
```
POST ajax-api/2.0/mlflow/model-versions/create
# Request:
{
  "name": "model-name",
  "source": "test-source-edit",  # Invalid - needs runs:/{run_id}/path format
  "description": "Version description"
}
# Current Response: 400 Bad Request (vague error)
```

**Suggested Response:**
```json
{
  "error_code": "INVALID_MODEL_SOURCE",
  "message": "Model version source must be a valid artifact URI",
  "details": {
    "valid_formats": ["runs:/<run_id>/<path>", "mlflow-artifacts:/<path>"],
    "provided_source": "test-source-edit"
  }
}
```

**Action Items:**
- [ ] Improve error message for invalid model version source
- [ ] Document valid source URI formats
- [ ] Consider allowing relative paths for simpler use cases

---

## 5. Permission API Design

### 5.1 Bulk Permission Operations
**Issue:** Tests must set permissions one-by-one, which is slow.

**Suggested New Endpoint:**
```
POST api/2.0/mlflow/permissions/bulk
# Request:
{
  "grants": [
    {"user": "alice@example.com", "resource_type": "experiment", "resource_id": "123", "permission": "READ"},
    {"user": "bob@example.com", "resource_type": "experiment", "resource_id": "123", "permission": "EDIT"},
    {"group": "data-scientists", "resource_type": "registered-model", "resource_id": "my-model", "permission": "READ"}
  ]
}
# Response:
{
  "results": [
    {"status": "created", "index": 0},
    {"status": "updated", "index": 1},
    {"status": "error", "index": 2, "error": "Group not found"}
  ]
}
```

**Action Items:**
- [ ] Add bulk permission endpoint: `POST /api/2.0/mlflow/permissions/bulk`
- [ ] Accept array of permission grants in single request
- [ ] Return partial success/failure results

### 5.2 Permission Query Endpoint
**Issue:** No easy way to check "what permission does user X have on resource Y?"

**Suggested New Endpoint:**
```
GET api/2.0/mlflow/permissions/check?user={username}&resource_type={type}&resource_id={id}
# Response:
{
  "user": "alice@example.com",
  "resource_type": "experiment",
  "resource_id": "123",
  "effective_permission": "EDIT",
  "source": "group",  // "user", "group", "regex", "group-regex", "default"
  "source_details": {
    "group_name": "data-scientists"
  }
}
```

**Action Items:**
- [ ] Add `GET /api/2.0/mlflow/permissions/check` endpoint
- [ ] Accept: `user`, `resource_type`, `resource_id`
- [ ] Return: effective permission and its source (user, group, regex, default)

### 5.3 List User's Effective Permissions
**Issue:** Can't easily see all resources a user can access.

**Suggested New Endpoint:**
```
GET api/2.0/mlflow/users/{username}/permissions
# Response:
{
  "user": "alice@example.com",
  "experiments": [
    {"id": "123", "name": "my-exp", "permission": "MANAGE", "source": "user"},
    {"id": "456", "name": "team-exp", "permission": "READ", "source": "group"}
  ],
  "registered_models": [...],
  "prompts": [...]
}
```

**Action Items:**
- [ ] Add `GET /api/2.0/mlflow/users/{username}/permissions` endpoint
- [ ] Return all experiments, models, prompts user can access
- [ ] Include permission source (direct, group, regex, default)

---

## 6. Resource Type Consistency

### 6.1 Prompts vs Registered Models
**Issue:** Prompts are implemented as tagged registered models, but permission APIs differ.

**Current Confusion:**
- Some endpoints use `registered-models` for prompts
- No dedicated prompt permission endpoints
- Prompts identified by `mlflow.prompt.is_prompt` tag

**Current Endpoints (prompts use model endpoints):**
```
# Creating a prompt:
POST ajax-api/2.0/mlflow/registered-models/create
# Body: {"name": "my-prompt", "tags": [{"key": "mlflow.prompt.is_prompt", "value": "true"}]}

POST ajax-api/2.0/mlflow/model-versions/create
# Body includes prompt text in tags

# Getting a prompt:
GET ajax-api/2.0/mlflow/registered-models/get?name={prompt_name}

# Prompt permissions use model permission endpoints:
POST/PATCH api/2.0/mlflow/permissions/users/{user}/registered-models/{prompt_name}
```

**Suggested: Dedicated Prompt Endpoints (or aliases):**
```
# Option A: Aliases that map to registered-models internally
POST api/2.0/mlflow/permissions/users/{user}/prompts/{prompt_name}
POST api/2.0/mlflow/permissions/groups/{group}/prompts/{prompt_name}

# Option B: Document clearly that prompts use registered-models API
```

**Action Items:**
- [ ] Add dedicated `/api/2.0/mlflow/permissions/*/prompts/*` endpoints (or document alias)
- [ ] Document that prompts use registered-model permissions
- [ ] Consider separating prompt permissions from model permissions

### 6.2 Scorers Permission Model
**Issue:** Unclear how scorer permissions work.

**Current Endpoints:**
```
# Register scorer:
POST ajax-api/2.0/mlflow/scorers/register
# Body: {"experiment_id": "123", "name": "my-scorer", "serialized_scorer": "..."}

# List scorers:
GET ajax-api/2.0/mlflow/scorers/list?experiment_id={id}
```

**Action Items:**
- [ ] Document scorer permission model
- [ ] Add scorer permission endpoints if separate from experiments
- [ ] Clarify inheritance (do scorers inherit experiment permissions?)

---

## 7. Health & Status Endpoints

### 7.1 Permission System Status
**Issue:** No way to verify permission system is working correctly.

**Current Health Endpoints:**
```
GET /health/live   # Basic liveness check
GET /health/ready  # Readiness check
```

**Suggested New Endpoint:**
```
GET /health/permissions
# Response:
{
  "status": "healthy",
  "permission_source_order": ["user", "group", "regex", "group-regex"],
  "default_permission": "MANAGE",
  "database": {
    "status": "connected",
    "type": "postgresql"
  },
  "stats": {
    "user_permissions_count": 150,
    "group_permissions_count": 25,
    "regex_permissions_count": 10
  }
}
```

**Action Items:**
- [ ] Add `/health/permissions` endpoint returning:
  - Permission source order
  - Default permission level
  - Database connectivity status
  - Cache status (if applicable)

---

## 8. API Documentation

### 8.1 Missing OpenAPI/Swagger Specs

**Current Permission Endpoints (need documentation):**
```
# User Permission Endpoints:
GET    api/2.0/mlflow/permissions/users/{username}/experiments/{experiment_id}
POST   api/2.0/mlflow/permissions/users/{username}/experiments/{experiment_id}
PATCH  api/2.0/mlflow/permissions/users/{username}/experiments/{experiment_id}
DELETE api/2.0/mlflow/permissions/users/{username}/experiments/{experiment_id}

GET    api/2.0/mlflow/permissions/users/{username}/registered-models/{model_name}
POST   api/2.0/mlflow/permissions/users/{username}/registered-models/{model_name}
PATCH  api/2.0/mlflow/permissions/users/{username}/registered-models/{model_name}
DELETE api/2.0/mlflow/permissions/users/{username}/registered-models/{model_name}

# Group Permission Endpoints:
GET    api/2.0/mlflow/permissions/groups/{group_name}/experiments/{experiment_id}
POST   api/2.0/mlflow/permissions/groups/{group_name}/experiments/{experiment_id}
DELETE api/2.0/mlflow/permissions/groups/{group_name}/experiments/{experiment_id}

GET    api/2.0/mlflow/permissions/groups/{group_name}/registered-models/{model_name}
POST   api/2.0/mlflow/permissions/groups/{group_name}/registered-models/{model_name}
DELETE api/2.0/mlflow/permissions/groups/{group_name}/registered-models/{model_name}

# Regex Permission Endpoints:
POST   api/2.0/mlflow/permissions/experiments/regex
POST   api/2.0/mlflow/permissions/registered-models/regex

# User Management Endpoints:
GET    api/2.0/mlflow/users
POST   api/2.0/mlflow/users
PATCH  api/2.0/mlflow/users/access-token
```

**Action Items:**
- [ ] Generate OpenAPI spec for all permission endpoints
- [ ] Include request/response examples
- [ ] Document error codes and their meanings
- [ ] Add authentication requirements per endpoint

### 8.2 Permission Level Documentation
**Action Items:**
- [ ] Document what each permission level allows:
  - READ: view, list
  - EDIT: view, list, create, update
  - MANAGE: view, list, create, update, delete, manage permissions
  - NO_PERMISSIONS: nothing
- [ ] Document priority/precedence rules

---

## 9. Test Infrastructure Gaps

These are issues we worked around in tests that should be fixed properly:

| Issue | Workaround Used | Endpoint Affected | Proper Fix Needed |
|-------|-----------------|-------------------|-------------------|
| Denied users return 302 | Accept 302 as denial | `POST ajax-api/2.0/mlflow/experiments/search` | Return 401 for API auth failure |
| 405 not in denial codes | Added 405 to `_is_denied()` | `PATCH ajax-api/2.0/mlflow/experiments/update` | Document or change behavior |
| peter@example.com blocked | Used different test user | N/A | N/A (test data issue) |
| Playwright sync in asyncio | Used fixtures from conftest | N/A | N/A (test structure) |
| Model version needs run | Create temp run first | `POST ajax-api/2.0/mlflow/model-versions/create` | Better error message |
| Group perm delete 500 | Ignore delete errors | `DELETE api/2.0/mlflow/permissions/groups/*/experiments/*` | Return 404 or 204 |

---

## 10. Security Considerations

### 10.1 Permission Enumeration
**Issue:** Can enumerate permissions by trying different resources.

**Affected Endpoints:**
```
# These endpoints reveal resource existence via different error codes:
GET ajax-api/2.0/mlflow/experiments/get?experiment_id={id}
# 404 = doesn't exist, 403 = exists but no access

GET ajax-api/2.0/mlflow/registered-models/get?name={name}
# Same issue
```

**Action Items:**
- [ ] Consider returning 404 instead of 403 for unauthorized resources (hide existence)
- [ ] Add rate limiting on permission check endpoints
- [ ] Audit logging for permission failures

### 10.2 Token Security

**Current Token Endpoint:**
```
PATCH api/2.0/mlflow/users/access-token
# Request: {"username": "user@example.com"}
# Response: {"token": "plain-text-token-value"}
```

**Action Items:**
- [ ] Add token expiration support
- [ ] Allow token scoping (read-only tokens, specific resources)
- [ ] Implement token revocation lists
- [ ] Consider adding `DELETE api/2.0/mlflow/users/access-token` for explicit revocation

---

## Priority Matrix

| Priority | Item | Effort | Impact |
|----------|------|--------|--------|
| P0 | Consistent denial status codes | Medium | High |
| P0 | Support Bearer token auth | Medium | High |
| P0 | Structured error responses | Medium | High |
| P1 | Fix 500 on missing group permission | Low | Medium |
| P1 | Return 401 (not 302) for API auth failures | Low | Medium |
| P1 | Experiment ID field consistency | Medium | Medium |
| P2 | Bulk permission operations | High | Medium |
| P2 | Permission check endpoint | Medium | Medium |
| P2 | OpenAPI documentation | High | High |
| P3 | Permission query endpoint | Medium | Low |
| P3 | Token expiration/scoping | High | Medium |

---

## Notes from Integration Tests

1. **API Prefix Pattern:** User management uses `api/2.0/mlflow/users`, permissions use `api/2.0/mlflow/permissions/...`

2. **MLflow Core APIs:** Use `ajax-api/2.0/mlflow/...` prefix (experiment/model/run operations)

3. **Authentication Methods Tested:**
   - Session cookies (from OIDC login)
   - Basic auth (username:token)
   - Bearer token (not working - needs fix)

4. **Permission Sources Tested:**
   - User-level permissions
   - Group-level permissions
   - Regex-based permissions
   - Default permissions

5. **Resources with Permissions:**
   - Experiments (experiment_id)
   - Registered Models (model name)
   - Prompts (model name with is_prompt tag)
   - Scorers (linked to experiments)
