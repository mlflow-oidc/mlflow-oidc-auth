---
applyTo: '**/*.py'
description: Python conventions — see AGENTS.md for the full set
---

Python conventions for this repository live in [`AGENTS.md`](../../AGENTS.md) and
[`mlflow_oidc_auth/AGENTS.md`](../../mlflow_oidc_auth/AGENTS.md). Read those; this file only
exists so Copilot applies them to `**/*.py`.

The short version:

- Black, line length **160**. Type hints on public signatures.
- Google/Sphinx docstrings with `Parameters` / `Returns` / `Raises` where intent is not obvious.
- Validate inputs early; raise specific exceptions. Never swallow an exception without a
  documented fallback.
- Module-level `logger = get_logger()`. Never log tokens, secrets, or full JWTs.
- New logic ships with tests, including a **negative** test whenever the change touches
  authentication, authorization, or permissions.
