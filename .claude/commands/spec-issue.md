---
description: Turn a rough idea into a self-contained, self-validating issue an agent can execute
argument-hint: <rough description of the work>
allowed-tools: Bash(gh:*), Bash(git:*), Read, Glob, Grep, Task
---

Turn this into an issue another agent can execute without asking anyone a question:

$ARGUMENTS

## Ground it first

Use `codebase-explorer` to find the files actually involved. An issue that names no real file is
not executable. Cite `path:line`.

## Write it to this shape

**Context** — why this exists and what is wrong today, with `file:line` references. Enough that
someone with no memory of this conversation can act.

**Scope** — what changes, as specific bullets. Also state what is explicitly *out* of scope; that
is what stops a diff from sprawling.

**Acceptance criteria** — the part that matters. Every criterion must be **a command that can be
run**, with its expected result. If you cannot express one as a command, it is an opinion — either
turn it into a check or cut it.

Bad: "permissions work correctly."
Good: `pytest mlflow_oidc_auth/tests/validators/test_experiment.py -k denies_without_grant` passes.

**Dependencies** — issues that must merge first, by number. Say if there are none.

**Security notes** — if the change touches auth, authz, sessions, tokens, permissions or CI: what
the failure mode is, and which negative test proves it cannot happen.

## Check it before proposing

- Could an agent with no prior context execute this? If it needs a decision only a human can
  make, put that decision in the issue as a stated assumption, or split the decision out.
- Is every criterion runnable?
- Is it one coherent change? If it is three, propose three issues and their dependency order.

Show the issue body and ask before running `gh issue create`. Never create it unprompted.
