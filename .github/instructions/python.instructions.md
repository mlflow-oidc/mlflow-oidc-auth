---
applyTo: '**/*.py'
description: Python coding conventions and guidelines
---

# Python Coding Conventions

## Functions and Types

- Require type hints on all function parameters and return values; use `typing` and `collections.abc` abstractions instead of concrete containers where possible.
- Keep functions small and single-purpose; extract helpers when a block becomes hard to scan.
- Provide PEP 257 docstrings with clear Parameters/Returns sections when intent is not obvious from the signature.
- Favor pure functions where practical; minimize hidden mutation and global state.

## Comments and Documentation

- Comment for intent and edge cases, not for restating code; briefly explain non-trivial algorithms or design choices.
- Document assumptions and expected invariants near the logic that depends on them.
- When using external libraries, note why the library is needed or any important configuration choices.

## Style and Formatting

- Follow PEP 8 and Black with the project limit of 160 characters; use 4 spaces for indentation.
- Place docstrings immediately after `def`/`class`; keep imports grouped by stdlib/third-party/local modules.
- Prefer f-strings for string formatting; avoid implicit string concatenation across lines.

## Error Handling

- Validate inputs early and raise specific exceptions with actionable messages; avoid silent failures.
- Log or attach context when catching exceptions, then re-raise or translate to a clearer error.
- Do not swallow exceptions unless there is a deliberate fallback path that is documented.

## Testing and Edge Cases

- Add or update unit tests for new logic and critical paths; keep tests deterministic and isolated.
- Cover edge cases such as empty inputs, invalid types, boundary values, and large datasets.
- Use descriptive test names and docstrings to convey the scenario and expectation.
