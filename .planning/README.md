# `.planning/`

Deep reference on the codebase. **This directory is not the roadmap and holds no plans.**

Current direction lives in GitHub issues — the active roadmap is
[epic #304 — enterprise identity](https://github.com/mlflow-oidc/mlflow-oidc-auth/issues/304).
Work is defined by [`.github/ISSUE_TEMPLATE/agent-task.yml`](../.github/ISSUE_TEMPLATE/agent-task.yml),
whose acceptance criteria are runnable commands. See
[`docs/agentic-development.md`](../docs/agentic-development.md).

## What is here

| File | Covers |
|---|---|
| `codebase/ARCHITECTURE.md` | Layers, data flow, key abstractions, entry points |
| `codebase/STRUCTURE.md` | Directory-by-directory map |
| `codebase/CONVENTIONS.md` | Full naming, style, import and documentation conventions |
| `codebase/TESTING.md` | Test layout, fixtures, how to run what |
| `codebase/INTEGRATIONS.md` | MLflow, identity providers, secret backends |
| `codebase/CONCERNS.md` | Known rough edges |

[`AGENTS.md`](../AGENTS.md) is the summary an agent reads first. These are what it consults when
the summary is not enough. **Where the two disagree, `AGENTS.md` wins** and the file here should
be corrected.

## What was removed, and where it went

This directory used to also hold milestone planning documents — `PROJECT.md`, `ROADMAP.md`,
`MILESTONES.md` and `REQUIREMENTS.md` — produced by a planning tool no longer wired into this
repository. They were removed once every requirement in them was verified shipped against the
code. The parts worth keeping moved out rather than being deleted:

| Content | Now lives in |
|---|---|
| Project constraints and core value | [`AGENTS.md`](../AGENTS.md) → *Constraints* |
| Workspace non-goals | [`docs/workspaces.md`](../docs/workspaces.md) → *Limitations and non-goals* |
| `PERMISSION_REGISTRY`, base permission repositories | `codebase/ARCHITECTURE.md` → *Key Abstractions* |
| Two deferred workspace UI enhancements | [issue #332](https://github.com/mlflow-oidc/mlflow-oidc-auth/issues/332) |

Nothing was salvaged from `ROADMAP.md`. Its enforcement behaviour is documented more completely
in `docs/workspaces.md` (which also covers trash and webhook scoping), its phase entries
referenced `NN-NN-PLAN.md` files that are not in this repository, and its success criteria cited
a `GRANT_DEFAULT_WORKSPACE_ACCESS` setting that does not exist in the code.

Everything else was process residue: phase counts, traceability tables, and a v1.0 accomplishments
list. Release history lives in git and in GitHub Releases and does not need a second copy here.

## The rule going forward

Do not add planning state here. A plan belongs in a GitHub issue where its acceptance criteria can
be checked; reference material belongs in `codebase/` or `docs/`. A second roadmap that nobody
updates is how the previous set of files ended up simultaneously complete and wrong.
