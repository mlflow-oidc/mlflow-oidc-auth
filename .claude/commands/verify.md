---
description: Run the full self-validation gate on the current working changes
allowed-tools: Bash(git:*), Bash(pytest:*), Bash(pre-commit run:*), Bash(yarn:*), Bash(black:*), Read, Glob, Grep, Task
---

Run the repository's definition of done against the current diff. Report results — do not fix
anything unless asked.

## 1. Scope

```bash
git status --short
git diff origin/main...HEAD --stat
```

## 2. Gates

```bash
pre-commit run --all-files
pytest mlflow_oidc_auth/tests/
```

Run backend tests per directory, and hook tests **per file** — `hooks/test_after_request.py`
hangs when the whole `hooks/` directory runs locally, while passing in CI.

If `web-react/` changed:

```bash
cd web-react && yarn lint && yarn test
```

## 3. Checks that are not a test command

- Auth/authz change without a **negative** test proving denial → fail.
- Migration that is not reversible, or a backfill inferring ownership it cannot know → fail.
- Secret, token, key or full JWT in the diff, including tests and fixtures → fail.
- A new query on the per-request auth path in `AuthMiddleware.dispatch` without justification →
  flag.
- New MLflow route with no validator in `hooks/before_request.py` → fail.
- Diff contains changes unrelated to the stated scope → flag.

## 4. Boundary changes

If the diff touches auth, authz, sessions, tokens, permissions, or `.github/workflows/`, run the
`security-reviewer` subagent and include its findings.

## 5. Report

A pass/fail line per gate with the command and its output on failure, then a single verdict.
Report failures plainly — a green summary over a red run is worse than no gate at all.
