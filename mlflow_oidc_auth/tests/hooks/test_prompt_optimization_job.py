"""Tests for PromptOptimizationJob before_request handler registration (ENTITY-01).

Verifies that all 5 PromptOptimizationJob protobuf RPCs are registered in
BEFORE_REQUEST_HANDLERS with the correct experiment-scoped validators.
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
    validate_can_delete_experiment,
)


class TestPromptOptimizationJobHandlers:
    """Verify PromptOptimizationJob proto handlers are registered correctly (ENTITY-01)."""

    def test_create_maps_to_update_experiment(self):
        """CreatePromptOptimizationJob requires EDIT on experiment (same as CreateRun)."""
        assert BEFORE_REQUEST_HANDLERS[CreatePromptOptimizationJob] is validate_can_update_experiment

    def test_get_maps_to_read_experiment(self):
        """GetPromptOptimizationJob requires READ on experiment."""
        assert BEFORE_REQUEST_HANDLERS[GetPromptOptimizationJob] is validate_can_read_experiment

    def test_search_maps_to_read_experiment(self):
        """SearchPromptOptimizationJobs requires READ on experiment."""
        assert BEFORE_REQUEST_HANDLERS[SearchPromptOptimizationJobs] is validate_can_read_experiment

    def test_delete_maps_to_delete_experiment(self):
        """DeletePromptOptimizationJob requires DELETE on experiment."""
        assert BEFORE_REQUEST_HANDLERS[DeletePromptOptimizationJob] is validate_can_delete_experiment

    def test_cancel_maps_to_update_experiment(self):
        """CancelPromptOptimizationJob requires EDIT on experiment (like cancelling a run)."""
        assert BEFORE_REQUEST_HANDLERS[CancelPromptOptimizationJob] is validate_can_update_experiment

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
