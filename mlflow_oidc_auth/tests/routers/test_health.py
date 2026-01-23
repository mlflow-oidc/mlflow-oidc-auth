"""
Comprehensive tests for the health check router.

This module tests all health check endpoints including ready, live, and startup
with various scenarios and response validation for Kubernetes probe support.
"""

from unittest.mock import patch, MagicMock

import pytest

from mlflow_oidc_auth.routers.health import health_check_router, health_check_ready, health_check_live, health_check_startup


class TestHealthCheckRouter:
    """Test class for health check router configuration."""

    def test_router_configuration(self):
        """Test that the health check router is properly configured."""
        assert health_check_router.prefix == "/health"
        assert health_check_router.tags == ["health"]
        assert 404 in health_check_router.responses
        assert health_check_router.responses[404]["description"] == "Not found"


class TestHealthCheckEndpoints:
    """Test class for health check endpoint functionality."""

    @pytest.mark.asyncio
    async def test_health_check_ready_all_healthy(self):
        """Test the ready health check endpoint when all checks pass."""
        with patch("mlflow_oidc_auth.routers.health.is_oidc_configured", return_value=True), patch("mlflow_oidc_auth.routers.health.store") as mock_store:
            mock_store.ping.return_value = True
            result = await health_check_ready()

            assert result.status_code == 200
            body = result.body.decode()
            assert "ready" in body
            assert "checks" in body

    @pytest.mark.asyncio
    async def test_health_check_ready_oidc_not_configured(self):
        """Test the ready health check when OIDC is not configured."""
        with patch("mlflow_oidc_auth.routers.health.is_oidc_configured", return_value=False), patch("mlflow_oidc_auth.routers.health.store") as mock_store:
            mock_store.ping.return_value = True
            result = await health_check_ready()

            assert result.status_code == 503
            body = result.body.decode()
            assert "not_ready" in body

    @pytest.mark.asyncio
    async def test_health_check_ready_database_not_available(self):
        """Test the ready health check when database is not available."""
        with patch("mlflow_oidc_auth.routers.health.is_oidc_configured", return_value=True), patch("mlflow_oidc_auth.routers.health.store") as mock_store:
            mock_store.ping.return_value = False
            result = await health_check_ready()

            assert result.status_code == 503
            body = result.body.decode()
            assert "not_ready" in body

    @pytest.mark.asyncio
    async def test_health_check_live(self):
        """Test the live health check endpoint."""
        result = await health_check_live()

        assert result.status_code == 200
        body = result.body.decode()
        assert "live" in body

    @pytest.mark.asyncio
    async def test_health_check_startup_initialized(self):
        """Test the startup health check when OIDC is initialized."""
        with patch("mlflow_oidc_auth.app.is_oidc_ready", return_value=True):
            result = await health_check_startup()

            assert result.status_code == 200
            body = result.body.decode()
            assert "started" in body

    @pytest.mark.asyncio
    async def test_health_check_startup_not_initialized(self):
        """Test the startup health check when OIDC is not initialized."""
        with patch("mlflow_oidc_auth.app.is_oidc_ready", return_value=False):
            result = await health_check_startup()

            assert result.status_code == 503
            body = result.body.decode()
            assert "initializing" in body


class TestHealthCheckIntegration:
    """Test class for health check integration with FastAPI."""

    def test_ready_endpoint_integration(self, client):
        """Test ready endpoint through FastAPI test client."""
        with patch("mlflow_oidc_auth.routers.health.is_oidc_configured", return_value=True), patch("mlflow_oidc_auth.routers.health.store") as mock_store:
            mock_store.ping.return_value = True
            response = client.get("/health/ready")

            assert response.status_code == 200
            json_response = response.json()
            assert json_response["status"] == "ready"
            assert "checks" in json_response

    def test_ready_endpoint_not_ready(self, client):
        """Test ready endpoint when checks fail."""
        with patch("mlflow_oidc_auth.routers.health.is_oidc_configured", return_value=False), patch("mlflow_oidc_auth.routers.health.store") as mock_store:
            mock_store.ping.return_value = True
            response = client.get("/health/ready")

            assert response.status_code == 503
            json_response = response.json()
            assert json_response["status"] == "not_ready"

    def test_live_endpoint_integration(self, client):
        """Test live endpoint through FastAPI test client."""
        response = client.get("/health/live")

        assert response.status_code == 200
        assert response.json() == {"status": "live"}

    def test_startup_endpoint_integration(self, client):
        """Test startup endpoint through FastAPI test client."""
        with patch("mlflow_oidc_auth.app.is_oidc_ready", return_value=True):
            response = client.get("/health/startup")

            assert response.status_code == 200
            json_response = response.json()
            assert json_response["status"] == "started"
            assert json_response["oidc_initialized"] is True

    def test_startup_endpoint_not_ready(self, client):
        """Test startup endpoint when OIDC is not initialized."""
        with patch("mlflow_oidc_auth.app.is_oidc_ready", return_value=False):
            response = client.get("/health/startup")

            assert response.status_code == 503
            json_response = response.json()
            assert json_response["status"] == "initializing"
            assert json_response["oidc_initialized"] is False

    def test_nonexistent_health_endpoint(self, client):
        """Test accessing non-existent health endpoint."""
        response = client.get("/health/nonexistent")

        assert response.status_code == 404

    def test_health_endpoints_content_type(self, client):
        """Test that health endpoints return proper content type."""
        # Live endpoint always returns 200
        response = client.get("/health/live")
        assert response.headers["content-type"] == "application/json"

    def test_health_endpoints_no_authentication_required(self, client):
        """Test that health endpoints don't require authentication."""
        # Live endpoint should work without any authentication
        response = client.get("/health/live")
        assert response.status_code == 200

    def test_health_endpoints_http_methods(self, client):
        """Test that health endpoints only accept GET requests."""
        # Test with live endpoint (always returns 200)
        endpoint = "/health/live"

        # GET should work
        response = client.get(endpoint)
        assert response.status_code == 200

        # POST should not be allowed
        response = client.post(endpoint)
        assert response.status_code == 405  # Method Not Allowed

        # PUT should not be allowed
        response = client.put(endpoint)
        assert response.status_code == 405  # Method Not Allowed

        # DELETE should not be allowed
        response = client.delete(endpoint)
        assert response.status_code == 405  # Method Not Allowed

    def test_health_endpoints_response_structure(self, client):
        """Test that all health endpoints return consistent response structure."""
        # Test live endpoint (simplest, always 200)
        response = client.get("/health/live")
        assert response.status_code == 200
        json_response = response.json()
        assert isinstance(json_response, dict)
        assert "status" in json_response
        assert json_response["status"] == "live"

    def test_health_endpoints_performance(self, client):
        """Test that health endpoints respond quickly."""
        import time

        # Test with live endpoint (simplest)
        endpoint = "/health/live"

        start_time = time.time()
        response = client.get(endpoint)
        end_time = time.time()

        assert response.status_code == 200
        # Health checks should be very fast (under 100ms)
        assert (end_time - start_time) < 0.1

    def test_health_endpoints_concurrent_requests(self, client):
        """Test that health endpoints handle concurrent requests properly."""
        import concurrent.futures

        def make_request(endpoint):
            return client.get(endpoint)

        # Test with live endpoint (always 200)
        endpoint = "/health/live"

        # Make concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for _ in range(5):
                future = executor.submit(make_request, endpoint)
                futures.append(future)

            # Wait for all requests to complete
            for future in concurrent.futures.as_completed(futures):
                response = future.result()
                assert response.status_code == 200
                assert "status" in response.json()

    def test_health_endpoints_with_query_parameters(self, client):
        """Test that health endpoints ignore query parameters."""
        # Test with live endpoint
        response = client.get("/health/live?param1=value1&param2=value2")
        assert response.status_code == 200
        assert response.json() == {"status": "live"}

    def test_health_endpoints_with_headers(self, client):
        """Test that health endpoints work with various headers."""
        headers = {"User-Agent": "Test-Agent/1.0", "Accept": "application/json", "X-Custom-Header": "test-value"}

        # Test with live endpoint
        response = client.get("/health/live", headers=headers)
        assert response.status_code == 200
        assert response.json() == {"status": "live"}
