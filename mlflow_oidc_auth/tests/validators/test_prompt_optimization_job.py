"""Tests for prompt optimization job validators."""

import json
from unittest.mock import MagicMock, patch

import pytest

from mlflow_oidc_auth.validators import prompt_optimization_job


class DummyPermission:
    def __init__(
        self,
        can_read=False,
        can_use=False,
        can_update=False,
        can_delete=False,
        can_manage=False,
    ):
        self.can_read = can_read
        self.can_use = can_use
        self.can_update = can_update
        self.can_delete = can_delete
        self.can_manage = can_manage


def _make_job_entity(experiment_id: str):
    """Create a mock job entity with the given experiment_id in its params."""
    job = MagicMock()
    job.params = json.dumps({"experiment_id": experiment_id})
    return job


def _patch_job_resolution(experiment_id: str = "exp-123", **perm_kwargs):
    """Context managers that patch get_request_param, get_job, and effective_experiment_permission."""
    return (
        patch(
            "mlflow_oidc_auth.validators.prompt_optimization_job.get_request_param",
            return_value="job-456",
        ),
        patch(
            "mlflow_oidc_auth.validators.prompt_optimization_job.get_job",
            return_value=_make_job_entity(experiment_id),
        ),
        patch(
            "mlflow_oidc_auth.validators.prompt_optimization_job.effective_experiment_permission",
            return_value=MagicMock(permission=DummyPermission(**perm_kwargs)),
        ),
    )


class TestGetPermissionFromPromptOptimizationJobId:
    """Tests for _get_permission_from_prompt_optimization_job_id resolver."""

    def test_resolves_experiment_id_from_job(self):
        """Should extract job_id, fetch job, parse experiment_id from params, and resolve permission."""
        p1, p2, p3 = _patch_job_resolution(experiment_id="exp-789", can_read=True)
        with p1 as mock_param, p2 as mock_get_job, p3 as mock_perm:
            perm = prompt_optimization_job._get_permission_from_prompt_optimization_job_id("alice")
            mock_param.assert_called_once_with("job_id")
            mock_get_job.assert_called_once_with("job-456")
            mock_perm.assert_called_once_with("exp-789", "alice")
            assert perm.can_read is True

    def test_uses_correct_experiment_id(self):
        """Should use the experiment_id from the job's params JSON."""
        job = MagicMock()
        job.params = json.dumps({"experiment_id": "exp-999", "other_param": "value"})
        with (
            patch(
                "mlflow_oidc_auth.validators.prompt_optimization_job.get_request_param",
                return_value="job-1",
            ),
            patch(
                "mlflow_oidc_auth.validators.prompt_optimization_job.get_job",
                return_value=job,
            ),
            patch(
                "mlflow_oidc_auth.validators.prompt_optimization_job.effective_experiment_permission",
                return_value=MagicMock(permission=DummyPermission(can_manage=True)),
            ) as mock_perm,
        ):
            prompt_optimization_job._get_permission_from_prompt_optimization_job_id("bob")
            mock_perm.assert_called_once_with("exp-999", "bob")


class TestValidateCanReadPromptOptimizationJob:
    """Tests for validate_can_read_prompt_optimization_job."""

    def test_returns_true_when_can_read(self):
        p1, p2, p3 = _patch_job_resolution(can_read=True)
        with p1, p2, p3:
            assert prompt_optimization_job.validate_can_read_prompt_optimization_job("alice") is True

    def test_returns_false_when_cannot_read(self):
        p1, p2, p3 = _patch_job_resolution(can_read=False)
        with p1, p2, p3:
            assert prompt_optimization_job.validate_can_read_prompt_optimization_job("alice") is False


class TestValidateCanUpdatePromptOptimizationJob:
    """Tests for validate_can_update_prompt_optimization_job (used for CancelPromptOptimizationJob)."""

    def test_returns_true_when_can_update(self):
        p1, p2, p3 = _patch_job_resolution(can_update=True)
        with p1, p2, p3:
            assert prompt_optimization_job.validate_can_update_prompt_optimization_job("alice") is True

    def test_returns_false_when_cannot_update(self):
        p1, p2, p3 = _patch_job_resolution(can_update=False)
        with p1, p2, p3:
            assert prompt_optimization_job.validate_can_update_prompt_optimization_job("alice") is False


class TestValidateCanDeletePromptOptimizationJob:
    """Tests for validate_can_delete_prompt_optimization_job."""

    def test_returns_true_when_can_delete(self):
        p1, p2, p3 = _patch_job_resolution(can_delete=True)
        with p1, p2, p3:
            assert prompt_optimization_job.validate_can_delete_prompt_optimization_job("alice") is True

    def test_returns_false_when_cannot_delete(self):
        p1, p2, p3 = _patch_job_resolution(can_delete=False)
        with p1, p2, p3:
            assert prompt_optimization_job.validate_can_delete_prompt_optimization_job("alice") is False


class TestBeforeRequestHandlerMappings:
    """Verify that before_request.py maps job protos to the correct validators."""

    def test_get_prompt_optimization_job_uses_job_validator(self):
        """GetPromptOptimizationJob should use validate_can_read_prompt_optimization_job, not validate_can_read_experiment."""
        from mlflow.protos.service_pb2 import GetPromptOptimizationJob
        from mlflow_oidc_auth.hooks.before_request import BEFORE_REQUEST_HANDLERS

        handler = BEFORE_REQUEST_HANDLERS[GetPromptOptimizationJob]
        assert handler.__name__ == "validate_can_read_prompt_optimization_job"

    def test_delete_prompt_optimization_job_uses_job_validator(self):
        """DeletePromptOptimizationJob should use validate_can_delete_prompt_optimization_job."""
        from mlflow.protos.service_pb2 import DeletePromptOptimizationJob
        from mlflow_oidc_auth.hooks.before_request import BEFORE_REQUEST_HANDLERS

        handler = BEFORE_REQUEST_HANDLERS[DeletePromptOptimizationJob]
        assert handler.__name__ == "validate_can_delete_prompt_optimization_job"

    def test_cancel_prompt_optimization_job_uses_job_validator(self):
        """CancelPromptOptimizationJob should use validate_can_update_prompt_optimization_job."""
        from mlflow.protos.service_pb2 import CancelPromptOptimizationJob
        from mlflow_oidc_auth.hooks.before_request import BEFORE_REQUEST_HANDLERS

        handler = BEFORE_REQUEST_HANDLERS[CancelPromptOptimizationJob]
        assert handler.__name__ == "validate_can_update_prompt_optimization_job"

    def test_create_prompt_optimization_job_still_uses_experiment_validator(self):
        """CreatePromptOptimizationJob should still use validate_can_update_experiment (carries experiment_id, no job yet)."""
        from mlflow.protos.service_pb2 import CreatePromptOptimizationJob
        from mlflow_oidc_auth.hooks.before_request import BEFORE_REQUEST_HANDLERS

        handler = BEFORE_REQUEST_HANDLERS[CreatePromptOptimizationJob]
        assert handler.__name__ == "validate_can_update_experiment"

    def test_search_prompt_optimization_jobs_still_uses_experiment_validator(self):
        """SearchPromptOptimizationJobs should still use validate_can_read_experiment (searches by experiment_id)."""
        from mlflow.protos.service_pb2 import SearchPromptOptimizationJobs
        from mlflow_oidc_auth.hooks.before_request import BEFORE_REQUEST_HANDLERS

        handler = BEFORE_REQUEST_HANDLERS[SearchPromptOptimizationJobs]
        assert handler.__name__ == "validate_can_read_experiment"
