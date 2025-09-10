"""
Comprehensive tests for the health check router.

This module tests all health check endpoints including ready, live, and startup
with various scenarios and response validation.
"""

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
    async def test_health_check_ready(self):
        """Test the ready health check endpoint."""
        result = await health_check_ready()

        assert result == {"status": "ready"}

    @pytest.mark.asyncio
    async def test_health_check_live(self):
        """Test the live health check endpoint."""
        result = await health_check_live()

        assert result == {"status": "live"}

    @pytest.mark.asyncio
    async def test_health_check_startup(self):
        """Test the startup health check endpoint."""
        result = await health_check_startup()

        assert result == {"status": "startup"}


class TestHealthCheckIntegration:
    """Test class for health check integration with FastAPI."""

    def test_ready_endpoint_integration(self, client):
        """Test ready endpoint through FastAPI test client."""
        response = client.get("/health/ready")

        assert response.status_code == 200
        assert response.json() == {"status": "ready"}

    def test_live_endpoint_integration(self, client):
        """Test live endpoint through FastAPI test client."""
        response = client.get("/health/live")

        assert response.status_code == 200
        assert response.json() == {"status": "live"}

    def test_startup_endpoint_integration(self, client):
        """Test startup endpoint through FastAPI test client."""
        response = client.get("/health/startup")

        assert response.status_code == 200
        assert response.json() == {"status": "startup"}

    def test_nonexistent_health_endpoint(self, client):
        """Test accessing non-existent health endpoint."""
        response = client.get("/health/nonexistent")

        assert response.status_code == 404

    def test_health_endpoints_content_type(self, client):
        """Test that health endpoints return proper content type."""
        endpoints = ["/health/ready", "/health/live", "/health/startup"]

        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.headers["content-type"] == "application/json"

    def test_health_endpoints_no_authentication_required(self, client):
        """Test that health endpoints don't require authentication."""
        # These should work without any authentication headers or session
        endpoints = ["/health/ready", "/health/live", "/health/startup"]

        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code == 200

    def test_health_endpoints_http_methods(self, client):
        """Test that health endpoints only accept GET requests."""
        endpoints = ["/health/ready", "/health/live", "/health/startup"]

        for endpoint in endpoints:
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
        endpoints_and_statuses = [("/health/ready", "ready"), ("/health/live", "live"), ("/health/startup", "startup")]

        for endpoint, expected_status in endpoints_and_statuses:
            response = client.get(endpoint)

            assert response.status_code == 200
            json_response = response.json()

            # Verify response structure
            assert isinstance(json_response, dict)
            assert "status" in json_response
            assert json_response["status"] == expected_status
            assert len(json_response) == 1  # Only status field should be present

    def test_health_endpoints_performance(self, client):
        """Test that health endpoints respond quickly."""
        import time

        endpoints = ["/health/ready", "/health/live", "/health/startup"]

        for endpoint in endpoints:
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

        endpoints = ["/health/ready", "/health/live", "/health/startup"]

        # Make concurrent requests to all endpoints
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for _ in range(5):  # 5 requests per endpoint
                for endpoint in endpoints:
                    future = executor.submit(make_request, endpoint)
                    futures.append(future)

            # Wait for all requests to complete
            for future in concurrent.futures.as_completed(futures):
                response = future.result()
                assert response.status_code == 200
                assert "status" in response.json()

    def test_health_endpoints_with_query_parameters(self, client):
        """Test that health endpoints ignore query parameters."""
        endpoints = ["/health/ready", "/health/live", "/health/startup"]
        expected_statuses = ["ready", "live", "startup"]

        for endpoint, expected_status in zip(endpoints, expected_statuses):
            # Test with various query parameters
            response = client.get(f"{endpoint}?param1=value1&param2=value2")

            assert response.status_code == 200
            assert response.json() == {"status": expected_status}

    def test_health_endpoints_with_headers(self, client):
        """Test that health endpoints work with various headers."""
        endpoints = ["/health/ready", "/health/live", "/health/startup"]
        expected_statuses = ["ready", "live", "startup"]

        headers = {"User-Agent": "Test-Agent/1.0", "Accept": "application/json", "X-Custom-Header": "test-value"}

        for endpoint, expected_status in zip(endpoints, expected_statuses):
            response = client.get(endpoint, headers=headers)

            assert response.status_code == 200
            assert response.json() == {"status": expected_status}
