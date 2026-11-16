"""Skill content on the artifact proxy (MLflow 3.18+).

MLflow stores a skill's uploaded content under ``skills/[@<organization>/]<name>/<token>/...`` and
its client pulls a skill by reading those paths through the artifact proxy. Reading them needs READ
on the skill; nothing but an administrator writes or deletes there (MLflow's server does that
itself); and every spelling that does not resolve to exactly one existing skill stays denied.

Driven through MLflow's real Flask routing table and the real ``before_request_hook``.
``DEFAULT_MLFLOW_PERMISSION`` is MANAGE here, so a denial never comes from a restrictive default.
"""

from types import SimpleNamespace

import pytest

pytest.importorskip("mlflow.store.tracking.skill_registry.artifact_paths", reason="MLflow's skill registry arrived in 3.18")

from mlflow.exceptions import MlflowException  # noqa: E402
from mlflow.protos.databricks_pb2 import RESOURCE_DOES_NOT_EXIST  # noqa: E402

from mlflow_oidc_auth.tests.hooks.authz_harness import (
    ADMIN,
    EDITOR,
    OUTSIDER,
    PREFIXES,
    READER,
    BaseFakeTrackingStore,
    allowed,
    denied,
    hook,
    install_permission_store,
)  # noqa: E402

TOKEN = "0123456789abcdef0123456789abcdef"
CONTENT = f"skills/reviewer/{TOKEN}/SKILL.md"
ORG_CONTENT = f"skills/@acme/reviewer/{TOKEN}/SKILL.md"


class _Skills(BaseFakeTrackingStore):
    """``reviewer`` and ``@acme/reviewer`` exist; nothing else does."""

    existing = {("", "reviewer"), ("acme", "reviewer")}

    def get_skill(self, name, organization=""):
        if (organization, name) not in self.existing:
            raise MlflowException("no such skill", error_code=RESOURCE_DOES_NOT_EXIST)
        return SimpleNamespace(name=name, organization=organization, workspace="default")


@pytest.fixture(autouse=True)
def permission_store(tmp_path, monkeypatch):
    from mlflow_oidc_auth.utils.permissions import flush_permission_cache

    s = install_permission_store(tmp_path, monkeypatch, _Skills())
    s.create_skill_permission("reviewer", READER, "READ")
    s.create_skill_permission("reviewer", EDITOR, "MANAGE")
    s.create_skill_permission("reviewer", OUTSIDER, "NO_PERMISSIONS")
    s.create_skill_permission("@acme/reviewer", OUTSIDER, "NO_PERMISSIONS")
    flush_permission_cache()
    yield s
    flush_permission_cache()


def _artifact(prefix, path):
    return f"{prefix}/2.0/mlflow-artifacts/artifacts/{path}"


def _list(prefix):
    return f"{prefix}/2.0/mlflow-artifacts/artifacts"


@pytest.mark.parametrize("prefix", PREFIXES)
class TestReadingSkillContent:
    def test_read_on_the_skill_downloads_its_content(self, prefix):
        assert allowed(hook(_artifact(prefix, CONTENT), "GET", READER))
        assert allowed(hook(_artifact(prefix, CONTENT), "HEAD", READER))

    def test_no_permission_on_the_skill_is_refused(self, prefix):
        assert denied(hook(_artifact(prefix, CONTENT), "GET", OUTSIDER))
        assert denied(hook(_artifact(prefix, CONTENT), "HEAD", OUTSIDER))

    def test_the_organization_twin_is_judged_on_its_own_grants(self, prefix):
        """READER holds READ on ``reviewer`` only; ``@acme/reviewer`` falls to the default."""
        assert denied(hook(_artifact(prefix, ORG_CONTENT), "GET", OUTSIDER))
        assert allowed(hook(_artifact(prefix, ORG_CONTENT), "GET", READER))

    def test_listing_a_skills_content_needs_read(self, prefix):
        assert allowed(hook(_list(prefix), "GET", READER, query={"path": f"skills/reviewer/{TOKEN}"}))
        assert denied(hook(_list(prefix), "GET", OUTSIDER, query={"path": f"skills/reviewer/{TOKEN}"}))

    def test_a_listing_cannot_smuggle_an_unreadable_skill(self, prefix):
        query = [("path", f"skills/reviewer/{TOKEN}"), ("path", f"skills/@acme/reviewer/{TOKEN}")]
        assert denied(hook(_list(prefix), "GET", OUTSIDER, query=query))

    def test_a_presigned_download_needs_read(self, prefix):
        path = f"{prefix}/2.0/mlflow-artifacts/presigned/{CONTENT}"
        assert allowed(hook(path, "GET", READER))
        assert denied(hook(path, "GET", OUTSIDER))

    def test_a_skill_that_does_not_exist_is_refused_whatever_the_default(self, prefix):
        """The default is MANAGE; a leftover tree of a deleted skill must not become readable by it."""
        assert denied(hook(_artifact(prefix, f"skills/gone/{TOKEN}/SKILL.md"), "GET", READER))
        assert denied(hook(_list(prefix), "GET", READER, query={"path": f"skills/gone/{TOKEN}"}))


@pytest.mark.parametrize("prefix", PREFIXES)
class TestNothingElseUnderTheUploadRoot:
    @pytest.mark.parametrize("method", ["PUT", "DELETE"])
    def test_nobody_but_an_admin_writes_or_deletes_skill_content(self, prefix, method):
        """Even MANAGE on the skill: MLflow's server stores and reclaims the content itself."""
        assert denied(hook(_artifact(prefix, CONTENT), method, EDITOR))
        assert denied(hook(_artifact(prefix, CONTENT), method, READER))
        assert allowed(hook(_artifact(prefix, CONTENT), method, ADMIN))

    @pytest.mark.parametrize("family", ["create", "complete", "abort"])
    def test_multipart_uploads_into_a_skill_are_refused(self, prefix, family):
        assert denied(hook(f"{prefix}/2.0/mlflow-artifacts/mpu/{family}/{CONTENT}", "POST", EDITOR, body={}))

    @pytest.mark.parametrize(
        "path",
        [
            "skills",  # the upload root names no skill
            "skills/@acme",  # nor does an organization
            f"workspaces/default/skills/reviewer/{TOKEN}/SKILL.md",  # only the workspace-relative spelling is recognized
            f"skills/./reviewer/{TOKEN}/SKILL.md",
            f"skills/Reviewer/{TOKEN}/SKILL.md",  # not a name MLflow stores
            f"Skills/reviewer/{TOKEN}/SKILL.md",
            f"./skills/reviewer/{TOKEN}/SKILL.md",
            f"skills%2Freviewer/{TOKEN}/SKILL.md".replace("%2F", "/@/"),
        ],
    )
    def test_a_spelling_that_names_no_single_skill_is_refused(self, prefix, path):
        assert denied(hook(_artifact(prefix, path), "GET", EDITOR))
        assert denied(hook(_list(prefix), "GET", EDITOR, query={"path": path}))

    def test_an_encoded_spelling_is_judged_as_mlflow_decodes_it(self, prefix):
        """``%2572eviewer`` decodes (twice) to ``reviewer``: the grants on ``reviewer`` decide."""
        path = f"skills/%2572eviewer/{TOKEN}/SKILL.md"
        assert denied(hook(_list(prefix), "GET", OUTSIDER, query={"path": path}))
        assert allowed(hook(_list(prefix), "GET", READER, query={"path": path}))
