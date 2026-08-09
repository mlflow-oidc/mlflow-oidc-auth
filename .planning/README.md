# `.planning/`

Long-form reference and historical planning records. **This directory is not the roadmap.**

Current direction lives in GitHub issues. The active roadmap is
[epic #304 — enterprise identity](https://github.com/mlflow-oidc/mlflow-oidc-auth/issues/304).
Work is defined by [`.github/ISSUE_TEMPLATE/agent-task.yml`](../.github/ISSUE_TEMPLATE/agent-task.yml),
whose acceptance criteria are runnable commands. See
[`docs/agentic-development.md`](../docs/agentic-development.md).

## Live reference

`codebase/` — deep reference on the codebase, linked from [`AGENTS.md`](../AGENTS.md). Read the
one you need; do not load all of them by default.

| File | Covers |
|---|---|
| `codebase/ARCHITECTURE.md` | Layers, data flow, key abstractions, entry points |
| `codebase/STRUCTURE.md` | Directory-by-directory map |
| `codebase/CONVENTIONS.md` | Full naming, style, import and documentation conventions |
| `codebase/TESTING.md` | Test layout, fixtures, how to run what |
| `codebase/INTEGRATIONS.md` | MLflow, identity providers, secret backends |
| `codebase/CONCERNS.md` | Known rough edges |

`AGENTS.md` is the summary an agent reads first. These are what it consults when the summary is
not enough. Where the two disagree, `AGENTS.md` wins and the file here should be corrected.

## Historical

These describe the **workspace milestone**, planned and shipped March 2026 under a previous
planning tool (GSD) that is no longer wired into this repository. They are kept as a record of
what was built and why. Do not read them as current direction, and do not add to them.

| File | Status |
|---|---|
| `PROJECT.md` | Workspace milestone framing. Historical. |
| `ROADMAP.md` | Workspace phases 1–8. Phases 7–8 shown as open were descoped, not scheduled. |
| `MILESTONES.md` | Record of what v1.0 workspace support shipped. Historical. |
| `REQUIREMENTS.md` | v1.1 workspace management requirements. Historical. |
