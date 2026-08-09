# CLAUDE.md

@AGENTS.md

Everything about this repository — architecture, commands, conventions, security rules, and how
to work as an agent here — lives in [`AGENTS.md`](AGENTS.md), the cross-tool standard file.
Subsystem detail is in [`mlflow_oidc_auth/AGENTS.md`](mlflow_oidc_auth/AGENTS.md) and
[`web-react/AGENTS.md`](web-react/AGENTS.md); the nearest file wins.

This file exists only for Claude Code specifics.

## Claude Code specifics

- **Permissions and guardrails**: `.claude/settings.json` (checked in, shared). Deny rules there
  are enforced at the tool layer and beat instructions in any markdown file — including this one.
- **Subagents**: `.claude/agents/` — `codebase-explorer`, `security-reviewer`, `finding-verifier`.
  All read-only. Fan them out for parallel investigation; give each a self-contained prompt.
- **Commands**: `.claude/commands/` — `/agent-task` to execute a GitHub issue end to end,
  `/verify` to run the full self-validation gate, `/spec-issue` to turn a rough idea into a
  self-contained, self-validating issue.
- **Process**: [`docs/agentic-development.md`](docs/agentic-development.md).

## Deep reference

`.planning/codebase/` holds the long-form generated reference: `ARCHITECTURE.md`,
`STRUCTURE.md`, `CONVENTIONS.md`, `TESTING.md`, `INTEGRATIONS.md`, `CONCERNS.md`. Read the one
you need for the task at hand rather than loading all of them.
