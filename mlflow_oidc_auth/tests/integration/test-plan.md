# Integration Test Plan - MLflow OIDC Auth Plugin

## Overview

This document defines the integration test plan for the MLflow OIDC Auth Plugin. Tests validate authentication, authorization, and permission enforcement across all resource types.

**OIDC Provider**: https://oidc-mock.technicaldomain.xyz/
**Admin User**: `frank@example.com` (member of `mlflow-admin` group)
**Cleanup Strategy**: No cleanup required - integration environment is recreated for each test run

---

## Test Users & Groups

**OIDC Provider**: https://oidc-mock.technicaldomain.xyz/

### User Matrix

| User | Email | Groups | Role Description |
|------|-------|--------|------------------|
| Alice | `alice@example.com` | `mlflow-users`, `experiments-reader`, `prompts-reader`, `models-reader` | READ permissions via groups |
| Bob | `bob@example.com` | `mlflow-users`, `experiments-editor`, `prompts-editor`, `models-editor` | EDIT permissions via groups |
| Charlie | `charlie@example.com` | `mlflow-users`, `experiments-manager`, `prompts-manager`, `models-manager` | MANAGE permissions via groups |
| Dave | `dave@example.com` | `mlflow-users`, `experiments-no-access`, `prompts-no-access`, `models-no-access` | NO_PERMISSIONS via groups |
| Eve | `eve@example.com` | `mlflow-users` | Default permissions (no explicit grants) |
| Frank | `frank@example.com` | `mlflow-admin` | Administrator |
| Peter | `peter@example.com` | `random-group` | Not in `mlflow-users` (access denied testing) |

### Service Accounts (Created During Tests)

| Account | Purpose |
|---------|---------|
| `svc-test-{uuid}@example.com` | Token-based API access testing |
| `svc-scorer-{uuid}@example.com` | Scorer seeding via tracking token |

---

## Test Categories

### 1. Authentication Tests (`test_authentication.py`)

#### 1.1 OIDC Login - Group Members
**Objective**: Verify all users in `mlflow-users` group can authenticate via OIDC

| Test ID | Test Case | Expected Result |
|---------|-----------|-----------------|
| AUTH-001 | Alice logs in via OIDC UI | Session cookie returned, user redirected to MLflow UI |
| AUTH-002 | Bob logs in via OIDC UI | Session cookie returned, user redirected to MLflow UI |
| AUTH-003 | Charlie logs in via OIDC UI | Session cookie returned, user redirected to MLflow UI |
| AUTH-004 | Dave logs in via OIDC UI | Session cookie returned, user redirected to MLflow UI |
| AUTH-005 | Eve logs in via OIDC UI | Session cookie returned, user redirected to MLflow UI |
| AUTH-006 | Frank (admin) logs in via OIDC UI | Session cookie returned, user redirected to MLflow UI |
| AUTH-007 | Peter (not in mlflow-users) logs in | Login denied or limited access (based on config) |

#### 1.2 Access Token Authentication
**Objective**: Verify access tokens work for API authentication

| Test ID | Test Case | Expected Result |
|---------|-----------|-----------------|
| AUTH-010 | User creates access token for themselves | Token returned, can be used for API calls |
| AUTH-011 | API call with valid Bearer token | Request authenticated, returns expected data |
| AUTH-012 | API call with invalid/expired token | 401 Unauthorized |
| AUTH-013 | Admin creates token for another user | Token returned, works for target user |
| AUTH-014 | Non-admin attempts to create token for another user | 403 Forbidden |

#### 1.3 Service Account Authentication
**Objective**: Verify service accounts can authenticate via tokens

| Test ID | Test Case | Expected Result |
|---------|-----------|-----------------|
| AUTH-020 | Admin creates service account | Service account created successfully |
| AUTH-021 | Admin creates token for service account | Token returned |
| AUTH-022 | Service account authenticates via token | Request authenticated |
| AUTH-023 | Service account creates experiment | Experiment created (if permissions allow) |
| AUTH-024 | Service account logs run with scorers | Run and scorer metrics logged |

---

### 2. Resource Creation Tests (`test_resource_creation.py`)

#### 2.1 Experiment Creation & Runs
**Objective**: Verify each user can create experiments with runs containing scorers

| Test ID | Test Case | User | Expected Result |
|---------|-----------|------|-----------------|
| RES-001 | Create experiment | All users | Experiment created, user is owner |
| RES-002 | Create run in own experiment | All users | Run created successfully |
| RES-003 | Log scorer metrics in run | All users | Scorer metrics logged (`scorer.response_length`, `scorer.contains_hello`) |
| RES-004 | Register scorers at experiment level | All users | Scorers registered for experiment |
| RES-005 | Create multiple runs with different scorers | All users | All runs contain expected scorer data |

#### 2.2 Model Creation
**Objective**: Verify each user can create registered models

| Test ID | Test Case | User | Expected Result |
|---------|-----------|------|-----------------|
| RES-010 | Create registered model | All users | Model created, user is owner |
| RES-011 | Create model version | All users | Version created for model |
| RES-012 | Update model description | Owner | Description updated |

#### 2.3 Prompt Creation
**Objective**: Verify each user can create prompts

| Test ID | Test Case | User | Expected Result |
|---------|-----------|------|-----------------|
| RES-020 | Create prompt (registered model with prompt tags) | All users | Prompt created, user is owner |
| RES-021 | Create prompt version with text | All users | Prompt version with text created |
| RES-022 | Update prompt with new version | Owner | New version created |

---

### 3. Permission Source Tests

#### 3.1 User-Level Permissions (`test_user_permissions.py`)
**Objective**: Verify direct user-to-resource permission grants work correctly

**Setup**: User1 (Alice) creates resources and grants explicit permissions to other users

| Test ID | Resource Type | Target User | Permission | Validation |
|---------|---------------|-------------|------------|------------|
| PERM-U-001 | Experiment | Bob | READ | Can view, cannot create run |
| PERM-U-002 | Experiment | Charlie | EDIT | Can view and create run, cannot delete |
| PERM-U-003 | Experiment | Dave | MANAGE | Can view, create run, delete, manage permissions |
| PERM-U-004 | Experiment | Dave | NO_PERMISSIONS | Cannot view (404), not in list |
| PERM-U-005 | Model | Bob | READ | Can view, cannot update |
| PERM-U-006 | Model | Charlie | EDIT | Can view and update, cannot delete |
| PERM-U-007 | Model | Eve | MANAGE | Full control including permission management |
| PERM-U-008 | Model | Dave | NO_PERMISSIONS | Cannot view (404), not in list |
| PERM-U-009 | Prompt | Bob | READ | Can view, cannot create version |
| PERM-U-010 | Prompt | Charlie | EDIT | Can view and create version |
| PERM-U-011 | Prompt | Eve | MANAGE | Full control |
| PERM-U-012 | Prompt | Dave | NO_PERMISSIONS | Cannot view (404), not in list |

#### 3.2 Group-Level Permissions (`test_group_permissions.py`)
**Objective**: Verify group membership grants correct permissions

**Setup**: Configure group permissions for test resources

| Test ID | Group | Resource Pattern | Permission | User (via membership) | Validation |
|---------|-------|------------------|------------|----------------------|------------|
| PERM-G-001 | `experiments-reader` | group-experiment | READ | Alice | Can view, cannot modify |
| PERM-G-002 | `experiments-editor` | group-experiment | EDIT | Bob | Can view and modify |
| PERM-G-003 | `experiments-manager` | group-experiment | MANAGE | Charlie | Full control |
| PERM-G-004 | `experiments-no-access` | group-experiment | NO_PERMISSIONS | Dave | Cannot access |
| PERM-G-005 | `models-reader` | group-model | READ | Alice | Can view only |
| PERM-G-006 | `models-editor` | group-model | EDIT | Bob | Can modify |
| PERM-G-007 | `models-manager` | group-model | MANAGE | Charlie | Full control |
| PERM-G-008 | `models-no-access` | group-model | NO_PERMISSIONS | Dave | Cannot access |
| PERM-G-009 | `prompts-reader` | group-prompt | READ | Alice | Can view only |
| PERM-G-010 | `prompts-editor` | group-prompt | EDIT | Bob | Can modify |
| PERM-G-011 | `prompts-manager` | group-prompt | MANAGE | Charlie | Full control |
| PERM-G-012 | `prompts-no-access` | group-prompt | NO_PERMISSIONS | Dave | Cannot access |
| PERM-G-013 | (none) | group-experiment | DEFAULT | Eve | Uses DEFAULT_MLFLOW_PERMISSION |

#### 3.3 Regex User Permissions (`test_regex_permissions.py`)
**Objective**: Verify regex pattern matching for user-specific permissions

**Setup**: Configure regex patterns for the authenticated user

| Test ID | Pattern | Resource Name | Permission | Validation |
|---------|---------|---------------|------------|------------|
| PERM-R-001 | `^prod-.*` | `prod-experiment-1` | NO_PERMISSIONS | User cannot access prod resources |
| PERM-R-002 | `^dev-.*` | `dev-experiment-1` | MANAGE | User has full control of dev resources |
| PERM-R-003 | `^staging-.*` | `staging-model-1` | EDIT | User can edit staging resources |
| PERM-R-004 | `^test-.*` | `test-prompt-1` | READ | User can only read test resources |
| PERM-R-005 | `.*-readonly$` | `feature-readonly` | READ | Suffix pattern matching works |
| PERM-R-006 | Pattern priority | Multiple matches | Highest priority wins | First matching pattern applied |

#### 3.4 Regex Group Permissions (`test_regex_group_permissions.py`)
**Objective**: Verify regex patterns applied at group level are inherited by members

| Test ID | Group | Pattern | Resource Name | Permission | Member User | Validation |
|---------|-------|---------|---------------|------------|-------------|------------|
| PERM-RG-001 | `experiments-reader` | `^regexp-group-.*` | `regexp-group-experiment` | READ | Alice | Inherited READ |
| PERM-RG-002 | `experiments-editor` | `^regexp-group-.*` | `regexp-group-experiment` | EDIT | Bob | Inherited EDIT |
| PERM-RG-003 | `experiments-manager` | `^regexp-group-.*` | `regexp-group-experiment` | MANAGE | Charlie | Inherited MANAGE |
| PERM-RG-004 | `experiments-no-access` | `^regexp-group-.*` | `regexp-group-experiment` | NO_PERMISSIONS | Dave | No access |

---

### 4. Permission Enforcement Tests (`test_permission_enforcement.py`)

#### 4.1 READ Permission Enforcement
**Objective**: Users with READ can only view, not modify

| Test ID | Action | Expected Result |
|---------|--------|-----------------|
| ENF-R-001 | GET experiment | 200 OK |
| ENF-R-002 | GET experiment runs | 200 OK |
| ENF-R-003 | POST create run | 403 Forbidden |
| ENF-R-004 | PATCH update experiment | 403 Forbidden |
| ENF-R-005 | DELETE experiment | 403 Forbidden |
| ENF-R-006 | POST/PATCH permission endpoint | 403 Forbidden |
| ENF-R-007 | GET model | 200 OK |
| ENF-R-008 | PATCH update model | 403 Forbidden |
| ENF-R-009 | DELETE model | 403 Forbidden |

#### 4.2 EDIT Permission Enforcement
**Objective**: Users with EDIT can view and modify, but not delete or manage permissions

| Test ID | Action | Expected Result |
|---------|--------|-----------------|
| ENF-E-001 | GET experiment | 200 OK |
| ENF-E-002 | POST create run | 200 OK |
| ENF-E-003 | PATCH update run | 200 OK |
| ENF-E-004 | DELETE experiment | 403 Forbidden |
| ENF-E-005 | DELETE run | 403 Forbidden |
| ENF-E-006 | POST/PATCH permission endpoint | 403 Forbidden |
| ENF-E-007 | GET model | 200 OK |
| ENF-E-008 | PATCH update model description | 200 OK |
| ENF-E-009 | DELETE model | 403 Forbidden |
| ENF-E-010 | POST create model version | 200 OK |

#### 4.3 MANAGE Permission Enforcement
**Objective**: Users with MANAGE have full control

| Test ID | Action | Expected Result |
|---------|--------|-----------------|
| ENF-M-001 | GET experiment | 200 OK |
| ENF-M-002 | POST create run | 200 OK |
| ENF-M-003 | DELETE run | 200 OK |
| ENF-M-004 | DELETE experiment | 200 OK |
| ENF-M-005 | POST grant permission to another user | 200 OK |
| ENF-M-006 | PATCH update permission | 200 OK |
| ENF-M-007 | DELETE revoke permission | 200 OK |
| ENF-M-008 | GET model | 200 OK |
| ENF-M-009 | PATCH update model | 200 OK |
| ENF-M-010 | DELETE model | 200 OK |

#### 4.4 NO_PERMISSIONS Enforcement
**Objective**: Users with NO_PERMISSIONS cannot access resources at all

| Test ID | Action | Expected Result |
|---------|--------|-----------------|
| ENF-N-001 | GET experiment by name | 404 Not Found (hidden) |
| ENF-N-002 | GET experiment by ID | 403/404 Forbidden/Not Found |
| ENF-N-003 | List experiments | Resource not in list |
| ENF-N-004 | POST create run | 403 Forbidden |
| ENF-N-005 | GET model | 404 Not Found (hidden) |
| ENF-N-006 | List models | Resource not in list |
| ENF-N-007 | GET prompt | 404 Not Found (hidden) |
| ENF-N-008 | List prompts | Resource not in list |

---

### 5. Admin Capabilities Tests (`test_admin_capabilities.py`)

#### 5.1 Admin Permission Management
**Objective**: Admin can manage permissions on any resource

| Test ID | Test Case | Expected Result |
|---------|-----------|-----------------|
| ADM-001 | Admin views any experiment | 200 OK |
| ADM-002 | Admin modifies any experiment | 200 OK |
| ADM-003 | Admin deletes any experiment | 200 OK |
| ADM-004 | Admin grants permission on any resource | 200 OK |
| ADM-005 | Admin revokes permission on any resource | 200 OK |
| ADM-006 | Admin overrides existing permission | 200 OK |

#### 5.2 Admin User Management
**Objective**: Admin can manage users and service accounts

| Test ID | Test Case | Expected Result |
|---------|-----------|-----------------|
| ADM-010 | Admin lists all users | User list returned |
| ADM-011 | Admin creates service account | Service account created |
| ADM-012 | Admin creates token for any user | Token returned |
| ADM-013 | Admin creates token for service account | Token returned |
| ADM-014 | Admin updates user attributes | User updated |

#### 5.3 Admin Bypasses All Restrictions
**Objective**: Admin is not restricted by permission rules

| Test ID | Test Case | Resource Owner | Permission to Admin | Expected Result |
|---------|-----------|----------------|---------------------|-----------------|
| ADM-020 | Admin accesses resource with NO_PERMISSIONS | Alice | NO_PERMISSIONS | 200 OK (admin bypass) |
| ADM-021 | Admin modifies READ-only resource | Alice | READ | 200 OK (admin bypass) |
| ADM-022 | Admin deletes resource without MANAGE | Alice | EDIT | 200 OK (admin bypass) |

---

### 6. Permission Source Priority Tests (`test_permission_priority.py`)

**Objective**: Verify `PERMISSION_SOURCE_ORDER=user,group,regex,group-regex` is respected

| Test ID | User Permission | Group Permission | Regex Permission | Group-Regex Permission | Expected Result |
|---------|-----------------|------------------|------------------|------------------------|-----------------|
| PRI-001 | MANAGE | READ | EDIT | NO_PERMISSIONS | MANAGE (user wins) |
| PRI-002 | (none) | EDIT | READ | MANAGE | EDIT (group wins) |
| PRI-003 | (none) | (none) | MANAGE | READ | MANAGE (regex wins) |
| PRI-004 | (none) | (none) | (none) | EDIT | EDIT (group-regex wins) |
| PRI-005 | (none) | (none) | (none) | (none) | DEFAULT_MLFLOW_PERMISSION |

---

### 7. Scorer Integration Tests (`test_scorers.py`)

**Objective**: Verify scorers work correctly with permissions

| Test ID | Test Case | Expected Result |
|---------|-----------|-----------------|
| SCO-001 | Owner registers scorers for experiment | Scorers registered |
| SCO-002 | Owner logs scorer metrics in run | Metrics logged |
| SCO-003 | READ user views runs with scorer metrics | Metrics visible |
| SCO-004 | EDIT user creates run with scorers | Run with scorers created |
| SCO-005 | Service account logs scorers via token | Scorers logged successfully |
| SCO-006 | NO_PERMISSIONS user cannot view scorer metrics | 403/404 |

---

### 8. Access Token Workflow Tests (`test_access_tokens.py`)

**Objective**: Complete access token lifecycle testing

| Test ID | Test Case | Actor | Expected Result |
|---------|-----------|-------|-----------------|
| TOK-001 | User creates own access token | Alice | Token returned |
| TOK-002 | Token used for experiment creation | Alice (via token) | Experiment created |
| TOK-003 | Token used for run logging | Alice (via token) | Run logged with metrics |
| TOK-004 | Token used for model operations | Alice (via token) | Model operations succeed |
| TOK-005 | Admin creates token for regular user | Frank → Alice | Token for Alice returned |
| TOK-006 | Admin creates token for service account | Frank → svc-account | Token returned |
| TOK-007 | Non-admin tries to create token for other | Alice → Bob | 403 Forbidden |
| TOK-008 | Token respects user's permissions | Alice (token) on Bob's resource | Permission enforced |

---

## Test Execution

### Prerequisites

1. MLflow OIDC Auth server running at `http://localhost:8080/`
2. OIDC mock provider accessible at `https://oidc-mock.technicaldomain.xyz/`
3. Playwright browsers installed (`playwright install chromium`)
4. Test users configured in OIDC mock provider

### Running Tests

```bash
# Run all integration tests
tox -e integration-live

# Run specific test category
pytest mlflow_oidc_auth/tests/integration/test_authentication.py -m integration

# Run with verbose output
pytest mlflow_oidc_auth/tests/integration -m integration -v

# Run with server requirement (fail instead of skip if server unavailable)
MLFLOW_OIDC_E2E_REQUIRE=1 pytest mlflow_oidc_auth/tests/integration -m integration
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MLFLOW_OIDC_E2E_BASE_URL` | `http://localhost:8080/` | Base URL of MLflow server |
| `MLFLOW_OIDC_E2E_REQUIRE` | `0` | If `1`, fail instead of skip on server unreachable |

---

## Test Data Naming Convention

To avoid conflicts between test runs, all test-created resources follow this pattern:

```
{user_email}-{resource_type}-{uuid}

Examples:
- alice@example.com-exp-a1b2c3d4
- bob@example.com-model-e5f6g7h8
- svc-test-i9j0k1l2@example.com-prompt-m3n4o5p6
```

---

## Permission Matrix Summary

| Permission | can_read | can_update | can_delete | can_manage | Visible in List |
|------------|----------|------------|------------|------------|-----------------|
| READ | ✅ | ❌ | ❌ | ❌ | ✅ |
| EDIT | ✅ | ✅ | ❌ | ❌ | ✅ |
| MANAGE | ✅ | ✅ | ✅ | ✅ | ✅ |
| NO_PERMISSIONS | ❌ | ❌ | ❌ | ❌ | ❌ |
| ADMIN | ✅ | ✅ | ✅ | ✅ | ✅ (all) |

---

## Test Dependencies Graph

```
test_authentication.py (no deps)
    ↓
test_resource_creation.py (requires: authenticated users)
    ↓
test_user_permissions.py (requires: resources created)
test_group_permissions.py (requires: resources + group config)
test_regex_permissions.py (requires: resources + regex config)
test_regex_group_permissions.py (requires: resources + group-regex config)
    ↓
test_permission_enforcement.py (requires: permissions configured)
test_permission_priority.py (requires: multiple permission sources)
    ↓
test_admin_capabilities.py (requires: permissions configured)
test_scorers.py (requires: experiments with runs)
test_access_tokens.py (requires: users + service accounts)
```

---

## Appendix: API Endpoints Reference

### Experiments
- `GET /ajax-api/2.0/mlflow/experiments/get-by-name?experiment_name=`
- `POST /ajax-api/2.0/mlflow/experiments/create`
- `DELETE /ajax-api/2.0/mlflow/experiments/delete`
- `POST /api/2.0/mlflow/runs/create`

### Models
- `GET /ajax-api/2.0/mlflow/registered-models/get?name=`
- `POST /ajax-api/2.0/mlflow/registered-models/create`
- `PATCH /ajax-api/2.0/mlflow/registered-models/update`
- `DELETE /ajax-api/2.0/mlflow/registered-models/delete`

### Prompts
- `POST /ajax-api/2.0/mlflow/registered-models/create` (with prompt tags)
- `POST /ajax-api/2.0/mlflow/model-versions/create` (with prompt text tag)

### Permissions
- `GET/POST/PATCH/DELETE /api/2.0/mlflow/permissions/users/{username}/experiments/{experiment_id}`
- `GET/POST/PATCH/DELETE /api/2.0/mlflow/permissions/users/{username}/registered-models/{model_name}`
- `GET/POST/PATCH/DELETE /api/2.0/mlflow/permissions/users/{username}/prompts/{prompt_name}`
- `POST /api/2.0/mlflow/groups/{group_name}/experiments/create`
- `POST /api/2.0/mlflow/groups/{group_name}/experiments/delete`

### Users & Tokens
- `GET /ajax-api/2.0/mlflow/users`
- `POST /ajax-api/2.0/mlflow/users`
- `PATCH /ajax-api/2.0/mlflow/users/access-token`

### Scorers
- `POST /ajax-api/2.0/mlflow/scorers/register`

### Health
- `GET /health/live`
