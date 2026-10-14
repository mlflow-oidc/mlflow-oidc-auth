"""The PR-title and commit-message checks must accept the same Conventional Commit types.

Squash merges use the PR title as the commit subject, so a type one check allows and the other
rejects blocks a merge (as `refactor` did before #477). Only the type lists are compared; the
title check's subject and header patterns have no counterpart in the commit check.
"""

from pathlib import Path

import pytest
import yaml

WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"


def _step_input(workflow: str, uses_prefix: str, key: str) -> str:
    if not WORKFLOWS.is_dir():
        pytest.skip("run from a source checkout: .github/workflows is not shipped in the package")
    data = yaml.safe_load((WORKFLOWS / workflow).read_text())
    for job in data["jobs"].values():
        for step in job.get("steps", []):
            if step.get("uses", "").startswith(uses_prefix):
                return step["with"][key]
    raise AssertionError(f"{workflow}: no step using {uses_prefix}")


def test_pr_title_and_commit_message_checks_allow_the_same_types():
    title_types = set(_step_input("pr-validate-title.yml", "amannn/action-semantic-pull-request", "types").split())
    commit_types = {t.strip() for t in _step_input("commit-message-check.yml", "webiny/action-conventional-commits", "allowed-commit-types").split(",")}
    assert title_types == commit_types
