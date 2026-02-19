# Permission System and Hierarchy

## Permission Levels

The system defines four permission levels with a hierarchical priority system:

### 1. READ Permission
- **Priority**: 1 (lowest hierarchy level)
- **Capabilities**:
  - `can_read: true`
  - `can_update: false`
  - `can_delete: false`
  - `can_manage: false`
- **Description**: Allows read-only access to resources

### 2. EDIT Permission
- **Priority**: 2 (medium hierarchy level)
- **Capabilities**:
  - `can_read: true`
  - `can_update: true`
  - `can_delete: false`
  - `can_manage: false`
- **Description**: Allows reading and updating resources

### 3. MANAGE Permission
- **Priority**: 3 (highest hierarchy level)
- **Capabilities**:
  - `can_read: true`
  - `can_update: true`
  - `can_delete: true`
  - `can_manage: true`
- **Description**: Full control over resources

### 4. NO_PERMISSIONS
- **Priority**: 100 (special case - no access)
- **Capabilities**:
  - `can_read: false`
  - `can_update: false`
  - `can_delete: false`
  - `can_manage: false`
- **Description**: No access to resources

## Permission Source Order

The `PERMISSION_SOURCE_ORDER` configuration controls the order in which permission sources are evaluated. The system checks each source in the specified order and uses the first permission found. If no explicit permission is found in any source, the system falls back to the default permission.

### Default Source Order
```
PERMISSION_SOURCE_ORDER=user,group,regex,group-regex
```

### Source Types

1. **`user`**: Direct user permissions for specific resources
2. **`group`**: Group-based permissions (users inherit from their groups)
3. **`regex`**: User-specific regex pattern permissions
4. **`group-regex`**: Group-based regex pattern permissions (users inherit regex permissions from their groups)

## Default Permission Behavior

When no explicit permission is found in any configured source, the system falls back to the default permission.

### Configuration
```bash
DEFAULT_MLFLOW_PERMISSION=MANAGE
```

### Default Values
- **Default**: `MANAGE`
- **Effect**: Users have full access to all resources unless explicitly restricted
- **Alternatives**: Can be set to `READ`, `EDIT`, or `NO_PERMISSIONS`


### Resolution Steps

1. **Iterate through sources** in `PERMISSION_SOURCE_ORDER`
2. **Query each source** for the specific resource and user
3. **Return first found permission** with source information
4. **Apply default permission** if no explicit permission exists
5. **Log permission source** for debugging and audit trails


### Example Priority Resolution

```python
# Users belong to groups with different permissions
Group A: experiment_123 -> READ (priority 1)
Group B: experiment_123 -> MANAGE (priority 3)

# Result: MANAGE permission (higher hierarchy level wins)
```

## Resource Creation Authorization

By default, any authenticated user can create experiments and registered models. This matches upstream MLflow behavior.

When `RESTRICT_RESOURCE_CREATION` is set to `true`, the system enforces permission checks on `CreateExperiment` and `CreateRegisteredModel` requests. The user must have at least **EDIT** permission (`can_update`) to create a resource.

### How creation permissions are resolved

Since the resource does not exist yet at creation time, only **name-based** permission sources apply:

1. **`regex`** — user-specific regex patterns matched against the new resource name
2. **`group-regex`** — group-based regex patterns matched against the new resource name
3. **Fallback** — `DEFAULT_MLFLOW_PERMISSION` if no regex pattern matches

> **Note:** The `user` and `group` sources are not used for creation checks because they are tied to existing resources (by experiment ID or model name) that don't exist yet.

### Configuration

```bash
# Enable creation permission checks (opt-in)
RESTRICT_RESOURCE_CREATION=true

# Combined with deny-by-default, only users with matching regex patterns can create resources
DEFAULT_MLFLOW_PERMISSION=NO_PERMISSIONS
```

### Affected endpoints

| Endpoint | Effect when restricted |
|----------|----------------------|
| `CreateExperiment` | Requires EDIT+ permission for the experiment name |
| `CreateRegisteredModel` | Requires EDIT+ permission for the model name |

Child resources (`CreateRun`, `CreateModelVersion`, etc.) are not affected — they inherit permissions from their parent resource.

## Regex Permission System

### Pattern Syntax
The system uses Python regular expression syntax:
- `.*` - Matches any experiment/model name
- `^prod-.*` - Matches names starting with "prod-"
- `.*-test$` - Matches names ending with "-test"
- `^(dev|test|staging)-.*` - Matches names starting with specific prefixes

### Priority System
- **Lower numbers** have higher priority
- **Priority 1** patterns are checked first
- **The first matching pattern** determines permission

### Example Regex Permissions

```python
# User regex permissions for experiments
Priority 1: "^prod-.*" -> NO_PERMISSIONS
Priority 2: "^dev-.*" -> MANAGE
Priority 3: ".*" -> READ

# For experiment "dev-ml-model":
# 1. Check "^prod-.*" -> No match
# 2. Check "^dev-.*" -> Match! -> MANAGE permission
```

## Configuration

### Environment Variables

```bash
# Permission source evaluation order
PERMISSION_SOURCE_ORDER="user,group,regex,group-regex"

# Default permission when no explicit permission found
DEFAULT_MLFLOW_PERMISSION="MANAGE"
```

### Alternative Configurations

```bash
# Security-first approach - deny by default
PERMISSION_SOURCE_ORDER="user,group,regex,group-regex"
DEFAULT_MLFLOW_PERMISSION="NO_PERMISSIONS"

# Group-priority approach
PERMISSION_SOURCE_ORDER="group,user,group-regex,regex"
DEFAULT_MLFLOW_PERMISSION="READ"

# Regex-first approach
PERMISSION_SOURCE_ORDER="regex,group-regex,user,group"
DEFAULT_MLFLOW_PERMISSION="READ"
```

## Examples

### Example 1: User with Direct Permission
```
User: alice
Resource: experiment_123
Sources:
- user: EDIT permission found
- group: (not checked - user permission found first)
Result: EDIT permission from user source
```

### Example 2: Group Inheritance
```
User: bob (member of dev-team, qa-team)
Resource: experiment_456
Sources:
- user: No permission found
- group: dev-team has MANAGE, qa-team has READ
Result: MANAGE permission (MANAGE hierarchy level 3 beats READ hierarchy level 1)
```

### Example 3: Regex Pattern Matching
```
User: charlie
Resource: prod-model-v1
Sources:
- user: No permission found
- group: No permission found
- regex: Pattern "^prod-.*" -> NO_PERMISSIONS
Result: NO_PERMISSIONS from regex source
```

### Example 4: Fallback to Default
```
User: diana
Resource: new-experiment
Sources:
- user: No permission found
- group: No permission found
- regex: No matching patterns
- group-regex: No matching patterns
Result: MANAGE permission from fallback (DEFAULT_MLFLOW_PERMISSION)
```

### Example 5: Resource Creation with RESTRICT_RESOURCE_CREATION
```
Config:
  RESTRICT_RESOURCE_CREATION=true
  DEFAULT_MLFLOW_PERMISSION=NO_PERMISSIONS

User: alice (member of ml-team)
Action: CreateExperiment with name "ml-team-training"
Group-regex for ml-team: "^ml-team-.*" -> EDIT

Resolution:
- regex: No matching user patterns
- group-regex: Pattern "^ml-team-.*" matches -> EDIT (can_update=true)
Result: Creation ALLOWED

User: bob (no group regex patterns)
Action: CreateExperiment with name "my-experiment"

Resolution:
- regex: No matching patterns
- group-regex: No matching patterns
- Fallback: NO_PERMISSIONS (can_update=false)
Result: Creation DENIED
```
