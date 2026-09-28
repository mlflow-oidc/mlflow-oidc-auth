# GitHub Copilot instructions

See [`AGENTS.md`](../AGENTS.md) in the repository root — it is the single source of truth for
architecture, commands, conventions, and the security rules that apply to AI agents in this
repository.

Subsystem detail lives in nested files, and the nearest one wins:

- [`mlflow_oidc_auth/AGENTS.md`](../mlflow_oidc_auth/AGENTS.md) — backend
- [`web-react/AGENTS.md`](../web-react/AGENTS.md) — frontend

Path-scoped Copilot rules remain in [`instructions/`](instructions/); they defer to `AGENTS.md`
wherever the two overlap.
