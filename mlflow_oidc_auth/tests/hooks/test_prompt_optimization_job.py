"""Tests for PromptOptimizationJob before_request handler registration (ENTITY-01).

Verifies that all 5 PromptOptimizationJob protobuf RPCs are registered in
BEFORE_REQUEST_HANDLERS with the correct validators — job-level validators
for Get/Delete/Cancel (which carry only job_id) and experiment-level validators
for Create/Search (which carry experiment_id).
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask, request
from mlflow.protos.service_pb2 import (
    CreatePromptOptimizationJob,
    GetPromptOptimizationJob,
    SearchPromptOptimizationJobs,
    DeletePromptOptimizationJob,
    CancelPromptOptimizationJob,
)

from mlflow_oidc_auth.hooks.before_request import BEFORE_REQUEST_HANDLERS
from mlflow_oidc_auth.validators import (
    validate_can_update_experiment,
    validate_can_read_experiment,
    validate_can_read_prompt_optimization_job,
    validate_can_delete_prompt_optimization_job,
    validate_can_update_prompt_optimization_job,
)
from mlflow_oidc_auth.validators import prompt_optimization_job as job_validator

app = Flask(__name__)


class TestPromptOptimizationJobHandlers:
    """Verify PromptOptimizationJob proto handlers are registered correctly (ENTITY-01)."""

    def test_create_maps_to_update_experiment(self):
        """CreatePromptOptimizationJob requires EDIT on experiment (same as CreateRun)."""
        assert BEFORE_REQUEST_HANDLERS[CreatePromptOptimizationJob] is validate_can_update_experiment

    def test_get_maps_to_read_prompt_optimization_job(self):
        """GetPromptOptimizationJob resolves job_id to experiment and requires READ."""
        assert BEFORE_REQUEST_HANDLERS[GetPromptOptimizationJob] is validate_can_read_prompt_optimization_job

    def test_search_maps_to_read_experiment(self):
        """SearchPromptOptimizationJobs requires READ on experiment (searches by experiment_id)."""
        assert BEFORE_REQUEST_HANDLERS[SearchPromptOptimizationJobs] is validate_can_read_experiment

    def test_delete_maps_to_delete_prompt_optimization_job(self):
        """DeletePromptOptimizationJob resolves job_id to experiment and requires DELETE."""
        assert BEFORE_REQUEST_HANDLERS[DeletePromptOptimizationJob] is validate_can_delete_prompt_optimization_job

    def test_cancel_maps_to_update_prompt_optimization_job(self):
        """CancelPromptOptimizationJob resolves job_id to experiment and requires UPDATE."""
        assert BEFORE_REQUEST_HANDLERS[CancelPromptOptimizationJob] is validate_can_update_prompt_optimization_job

    def test_all_five_protos_present(self):
        """All 5 PromptOptimizationJob protos are keys in BEFORE_REQUEST_HANDLERS."""
        expected = {
            CreatePromptOptimizationJob,
            GetPromptOptimizationJob,
            SearchPromptOptimizationJobs,
            DeletePromptOptimizationJob,
            CancelPromptOptimizationJob,
        }
        assert expected.issubset(set(BEFORE_REQUEST_HANDLERS.keys()))


class TestPromptOptimizationJobIdSource:
    """job_id must be read from the URL path — the identifier MLflow dispatches on."""

    def _perm(self, **flags):
        perm = MagicMock()
        for k, v in flags.items():
            setattr(perm.permission, k, v)
        return perm

    def test_job_id_read_from_path_not_body(self):
        """A body job_id must never override the path job_id (cross-source bypass)."""
        job = MagicMock()
        job.params = json.dumps({"experiment_id": "exp-victim"})
        with app.test_request_context(
            path="/api/3.0/mlflow/prompt-optimization/jobs/VICTIM_JOB",
            method="DELETE",
            json={"job_id": "OWN_JOB"},
            content_type="application/json",
        ):
            request.view_args = {"job_id": "VICTIM_JOB"}
            with (
                patch.object(job_validator, "get_job", return_value=job) as mock_get_job,
                patch.object(
                    job_validator,
                    "effective_experiment_permission",
                    return_value=self._perm(can_delete=False),
                ),
            ):
                assert validate_can_delete_prompt_optimization_job("attacker") is False
                # Resolution used the path job, not the attacker's body job.
                mock_get_job.assert_called_once_with("VICTIM_JOB")

    def test_job_id_resolves_permission_from_path(self):
        job = MagicMock()
        job.params = json.dumps({"experiment_id": "exp1"})
        with app.test_request_context(
            path="/api/3.0/mlflow/prompt-optimization/jobs/JOB123",
            method="GET",
        ):
            request.view_args = {"job_id": "JOB123"}
            with (
                patch.object(job_validator, "get_job", return_value=job) as mock_get_job,
                patch.object(
                    job_validator,
                    "effective_experiment_permission",
                    return_value=self._perm(can_read=True),
                ),
            ):
                assert validate_can_read_prompt_optimization_job("user1") is True
                mock_get_job.assert_called_once_with("JOB123")
