---
status: partial
phase: 02-workspace-auth-enforcement
source: [02-VERIFICATION.md]
started: 2026-03-23T22:30:00Z
updated: 2026-03-23T22:30:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. End-to-end workspace permission enforcement
expected: Enable `MLFLOW_ENABLE_WORKSPACES=True`, create a workspace, assign a user READ permission. Experiments in the permitted workspace are accessible; experiments in other workspaces return 403 or NO_PERMISSIONS.
result: [pending]

### 2. Workspace creation gating with real requests
expected: With workspaces enabled, send POST to /api/2.0/mlflow/experiments/create with and without workspace MANAGE permission. Without MANAGE → 403; with MANAGE → experiment created.
result: [pending]

### 3. ListWorkspaces after_request filtering
expected: As non-admin user with permission on workspace A but not B, call ListWorkspaces. Response only includes workspace A.
result: [pending]

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps
