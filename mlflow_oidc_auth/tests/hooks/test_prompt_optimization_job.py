"""Tests for PromptOptimizationJob before_request handler registration (ENTITY-01).

Verifies that all 5 PromptOptimizationJob protobuf RPCs are registered in
BEFORE_REQUEST_HANDLERS with the correct validators — job-level validators
for Get/Delete/Cancel (which carry only job_id) and experiment-level validators
for Create/Search (which carry experiment_id).
"""

import pytest
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
