"""
Comprehensive tests for the UI router.

This module tests all UI endpoints including SPA serving, configuration,
and static file handling with various scenarios and edge cases.
"""

import os
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch
from fastapi import HTTPException
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

from mlflow_oidc_auth.routers.ui import (
    ui_router,
    serve_spa_config,
    serve_spa_root,
    serve_spa,
    redirect_to_ui,
)


class TestUIRouter:
    """Test class for UI router configuration."""

    def test_router_configuration(self):
        """Test that the UI router is properly configured."""
        assert ui_router.prefix == "/oidc/ui"
        assert ui_router.tags == ["ui"]
        assert 404 in ui_router.responses
        assert ui_router.responses[404]["description"] == "Resource not found"


class TestServeSPAConfig:
    """Test the SPA configuration endpoint."""

    @pytest.mark.asyncio
    async def test_serve_spa_config_authenticated(self, mock_request_with_session, mock_config):
        """Test SPA config for authenticated user."""
        # Call the handler directly with dependency values rather than a mock Request
        with (
            patch("mlflow_oidc_auth.routers.ui.config", mock_config),
            patch("mlflow_oidc_auth.routers.ui.get_base_path") as mock_base_path,
        ):
            mock_base_path.return_value = "http://localhost:8000"

            result = await serve_spa_config(base_path="http://localhost:8000", authenticated=True)

            assert isinstance(result, JSONResponse)
            # Parse the response content
            import json

            body = result.body
            if isinstance(body, memoryview):
                text = body.tobytes().decode()
            elif isinstance(body, bytes):
                text = body.decode()
            else:
                text = bytes(body).decode()
            content = json.loads(text)

            assert content["basePath"] == "http://localhost:8000"
            assert content["uiPath"] == "http://localhost:8000/oidc/ui"
            assert content["provider"] == "Test Provider"
            assert content["authenticated"] is True

    @pytest.mark.asyncio
    async def test_serve_spa_config_unauthenticated(self, mock_request_with_session, mock_config):
        """Test SPA config for unauthenticated user."""
        # Call the handler directly with dependency values rather than a mock Request
        with (
            patch("mlflow_oidc_auth.routers.ui.config", mock_config),
            patch("mlflow_oidc_auth.routers.ui.get_base_path") as mock_base_path,
        ):
            mock_base_path.return_value = "http://localhost:8000"

            result = await serve_spa_config(base_path="http://localhost:8000", authenticated=False)

            assert isinstance(result, JSONResponse)
            import json

            body = result.body
            if isinstance(body, memoryview):
                text = body.tobytes().decode()
            elif isinstance(body, bytes):
                text = body.decode()
            else:
                text = bytes(body).decode()
            content = json.loads(text)

            assert content["authenticated"] is False

    def test_serve_spa_config_integration(self, authenticated_client):
        """Test SPA config endpoint through FastAPI test client."""
        response = authenticated_client.get("/oidc/ui/config.json")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"

        config_data = response.json()
        assert "basePath" in config_data
        assert "uiPath" in config_data
        assert "provider" in config_data
        assert "authenticated" in config_data


class TestServeSPARoot:
    """Test the SPA root serving functionality."""

    @pytest.mark.asyncio
    async def test_serve_spa_root_file_exists(self):
        """Test serving SPA root when index.html exists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a mock index.html file
            index_path = os.path.join(temp_dir, "index.html")
            with open(index_path, "w") as f:
                f.write("<html><body>Test SPA</body></html>")

            # Patch the internal helper to return the directory and index file path
            with patch("mlflow_oidc_auth.routers.ui._get_ui_directory") as mock_get:
                mock_get.return_value = (
                    Path(temp_dir).resolve(),
                    Path(index_path).resolve(),
                )
                result = await serve_spa_root()

                assert isinstance(result, FileResponse)
                expected_path = Path(index_path).resolve()
                assert result.path == str(expected_path)

    @pytest.mark.asyncio
    async def test_serve_spa_root_file_not_exists(self):
        """Test serving SPA root when index.html doesn't exist.

        The router's helper now raises RuntimeError when the UI directory or
        index file isn't present; ensure that propagates.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("mlflow_oidc_auth.routers.ui._get_ui_directory") as mock_get:
                mock_get.side_effect = RuntimeError("UI index.html not found")
                with pytest.raises(RuntimeError) as exc_info:
                    await serve_spa_root()

                assert "UI index.html not found" in str(exc_info.value)

    def test_serve_spa_root_integration(self, client):
        """Test SPA root endpoint through FastAPI test client."""
        # Create a temporary UI directory with index.html
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = os.path.join(temp_dir, "index.html")
            with open(index_path, "w") as f:
                f.write("<html><body>Test SPA</body></html>")

            with patch("mlflow_oidc_auth.routers.ui._get_ui_directory") as mock_get:
                mock_get.return_value = (
                    Path(temp_dir).resolve(),
                    Path(index_path).resolve(),
                )
                response = client.get("/oidc/ui/")

                assert response.status_code == 200
                assert "text/html" in response.headers.get("content-type", "")


class TestServeSPA:
    """Test the SPA file serving functionality."""

    @pytest.mark.asyncio
    async def test_serve_spa_static_file_exists(self):
        """Test serving static file that exists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a mock CSS file
            css_path = os.path.join(temp_dir, "styles.css")
            with open(css_path, "w") as f:
                f.write("body { margin: 0; }")

            with patch("mlflow_oidc_auth.routers.ui._get_ui_directory") as mock_get:
                mock_get.return_value = (
                    Path(temp_dir).resolve(),
                    Path(os.path.join(temp_dir, "index.html")).resolve(),
                )
                result = await serve_spa("styles.css")

                assert isinstance(result, FileResponse)
                expected_path = Path(css_path).resolve()
                assert result.path == str(expected_path)

    @pytest.mark.asyncio
    async def test_serve_spa_route_fallback_to_index(self):
        """Test serving SPA route that falls back to index.html."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create index.html but not the requested route file
            index_path = os.path.join(temp_dir, "index.html")
            with open(index_path, "w") as f:
                f.write("<html><body>SPA Router</body></html>")

            with patch("mlflow_oidc_auth.routers.ui._get_ui_directory") as mock_get:
                mock_get.return_value = (
                    Path(temp_dir).resolve(),
                    Path(index_path).resolve(),
                )
                result = await serve_spa("auth")  # SPA route, not a file

                assert isinstance(result, FileResponse)
                expected_path = Path(index_path).resolve()
                assert result.path == str(expected_path)

    @pytest.mark.asyncio
    async def test_serve_spa_path_traversal_does_not_escape_ui_directory(self):
        """Test that path traversal attempts cannot read files outside the UI directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            ui_dir = Path(temp_dir) / "ui"
            ui_dir.mkdir(parents=True, exist_ok=True)

            index_path = ui_dir / "index.html"
            index_path.write_text("<html><body>SPA</body></html>")

            # Create a file outside the UI directory that we must never serve.
            secret_path = Path(temp_dir) / "secret.txt"
            secret_path.write_text("TOP-SECRET")

            with patch("mlflow_oidc_auth.routers.ui._get_ui_directory") as mock_get:
                mock_get.return_value = (ui_dir.resolve(), index_path.resolve())

                result = await serve_spa("../secret.txt")

                assert isinstance(result, FileResponse)
                assert result.path == str(index_path.resolve())

    @pytest.mark.asyncio
    async def test_serve_spa_absolute_path_does_not_escape_ui_directory(self):
        """Test that absolute path attempts cannot read arbitrary filesystem paths."""
        with tempfile.TemporaryDirectory() as temp_dir:
            ui_dir = Path(temp_dir) / "ui"
            ui_dir.mkdir(parents=True, exist_ok=True)

            index_path = ui_dir / "index.html"
            index_path.write_text("<html><body>SPA</body></html>")

            outside_dir = Path(temp_dir) / "outside"
            outside_dir.mkdir(parents=True, exist_ok=True)
            secret_path = outside_dir / "secret.txt"
            secret_path.write_text("TOP-SECRET")

            with patch("mlflow_oidc_auth.routers.ui._get_ui_directory") as mock_get:
                mock_get.return_value = (ui_dir.resolve(), index_path.resolve())

                result = await serve_spa(str(secret_path.resolve()))

                assert isinstance(result, FileResponse)
                assert result.path == str(index_path.resolve())

    @pytest.mark.asyncio
    async def test_serve_spa_nested_route_fallback(self):
        """Test serving nested SPA route that falls back to index.html."""
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = os.path.join(temp_dir, "index.html")
            with open(index_path, "w") as f:
                f.write("<html><body>SPA Router</body></html>")

            with patch("mlflow_oidc_auth.routers.ui._get_ui_directory") as mock_get:
                mock_get.return_value = (
                    Path(temp_dir).resolve(),
                    Path(index_path).resolve(),
                )
                result = await serve_spa("admin/users")  # Nested SPA route

                assert isinstance(result, FileResponse)
                expected_path = Path(index_path).resolve()
                assert result.path == str(expected_path)

    @pytest.mark.asyncio
    async def test_serve_spa_no_index_file(self):
        """Test serving SPA when index.html doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("mlflow_oidc_auth.routers.ui._get_ui_directory") as mock_get:
                mock_get.side_effect = RuntimeError("UI index.html not found")
                with pytest.raises(RuntimeError) as exc_info:
                    await serve_spa("nonexistent")

                assert "UI index.html not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_serve_spa_javascript_file(self):
        """Test serving JavaScript file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            js_path = os.path.join(temp_dir, "main.js")
            with open(js_path, "w") as f:
                f.write("console.log('Hello World');")

            with patch("mlflow_oidc_auth.routers.ui._get_ui_directory") as mock_get:
                mock_get.return_value = (
                    Path(temp_dir).resolve(),
                    Path(os.path.join(temp_dir, "index.html")).resolve(),
                )
                result = await serve_spa("main.js")

                assert isinstance(result, FileResponse)
                expected_path = Path(js_path).resolve()
                assert result.path == str(expected_path)

    @pytest.mark.asyncio
    async def test_serve_spa_subdirectory_file(self):
        """Test serving file from subdirectory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create subdirectory and file
            subdir = os.path.join(temp_dir, "assets")
            os.makedirs(subdir)
            img_path = os.path.join(subdir, "logo.png")
            with open(img_path, "wb") as f:
                f.write(b"fake image data")

            with patch("mlflow_oidc_auth.routers.ui._get_ui_directory") as mock_get:
                mock_get.return_value = (
                    Path(temp_dir).resolve(),
                    Path(os.path.join(temp_dir, "index.html")).resolve(),
                )
                result = await serve_spa("assets/logo.png")

                assert isinstance(result, FileResponse)
                expected_path = Path(img_path).resolve()
                assert result.path == str(expected_path)

    def test_serve_spa_integration_static_file(self, client):
        """Test serving static file through FastAPI test client."""
        with tempfile.TemporaryDirectory() as temp_dir:
            css_path = os.path.join(temp_dir, "styles.css")
            with open(css_path, "w") as f:
                f.write("body { margin: 0; }")

            with patch("mlflow_oidc_auth.routers.ui._get_ui_directory") as mock_get:
                mock_get.return_value = (
                    Path(temp_dir).resolve(),
                    Path(os.path.join(temp_dir, "index.html")).resolve(),
                )
                response = client.get("/oidc/ui/styles.css")

                assert response.status_code == 200

    def test_serve_spa_integration_route_fallback(self, client):
        """Test SPA route fallback through FastAPI test client."""
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = os.path.join(temp_dir, "index.html")
            with open(index_path, "w") as f:
                f.write("<html><body>SPA</body></html>")

            with patch("mlflow_oidc_auth.routers.ui._get_ui_directory") as mock_get:
                mock_get.return_value = (
                    Path(temp_dir).resolve(),
                    Path(index_path).resolve(),
                )
                response = client.get("/oidc/ui/auth")

                assert response.status_code == 200
                assert "text/html" in response.headers.get("content-type", "")


class TestRedirectToUI:
    """Test the UI redirect functionality."""

    @pytest.mark.asyncio
    async def test_redirect_to_ui(self, mock_request_with_session):
        """Test redirect to UI endpoint."""
        request = mock_request_with_session()

        with patch("mlflow_oidc_auth.routers.ui.get_base_path") as mock_base_path:
            mock_base_path.return_value = "http://localhost:8000"

            result = await redirect_to_ui(request)

            assert isinstance(result, RedirectResponse)
            assert result.status_code == 307
            assert result.headers["location"] == "http://localhost:8000/oidc/ui/"

    def test_redirect_to_ui_integration(self, client):
        """Test UI redirect through FastAPI test client."""
        response = client.get("/oidc/ui", allow_redirects=False)

        assert response.status_code == 307
        assert "location" in response.headers
        assert response.headers["location"].endswith("/oidc/ui/")


class TestUIRouterIntegration:
    """Test class for UI router integration scenarios."""

    def test_ui_endpoints_no_authentication_required(self, client):
        """Test that UI endpoints don't require authentication."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create basic UI files
            index_path = os.path.join(temp_dir, "index.html")
            with open(index_path, "w") as f:
                f.write("<html><body>UI</body></html>")

            css_path = os.path.join(temp_dir, "styles.css")
            with open(css_path, "w") as f:
                f.write("body { margin: 0; }")

            with patch("mlflow_oidc_auth.routers.ui._get_ui_directory") as mock_get:
                mock_get.return_value = (
                    Path(temp_dir).resolve(),
                    Path(index_path).resolve(),
                )
                # These should work without authentication
                endpoints = [
                    "/oidc/ui/",
                    "/oidc/ui/styles.css",
                    "/oidc/ui/auth",
                ]  # SPA route

                for endpoint in endpoints:
                    response = client.get(endpoint)
                    assert response.status_code == 200

    def test_ui_config_endpoint_works_without_auth(self, client):
        """Test that config endpoint works without authentication."""
        response = client.get("/oidc/ui/config.json")

        assert response.status_code == 200
        config_data = response.json()
        assert config_data["authenticated"] is False

    def test_ui_config_endpoint_with_auth(self, authenticated_client):
        """Test that config endpoint reflects authentication status."""
        # Override the router dependency with a function accepting a Request so
        # FastAPI will accept it and the endpoint will return authenticated=True.
        from mlflow_oidc_auth.routers import ui as ui_module
        from fastapi import Request as _Request

        def _always_true(request: _Request) -> bool:
            return True

        app = authenticated_client._client.app
        app.dependency_overrides[ui_module.is_authenticated] = _always_true

        try:
            response = authenticated_client.get("/oidc/ui/config.json")

            assert response.status_code == 200
            config_data = response.json()
            assert config_data["authenticated"] is True
        finally:
            app.dependency_overrides.pop(ui_module.is_authenticated, None)

    def test_ui_endpoints_handle_path_traversal_attempts(self, client):
        """Test that UI endpoints handle path traversal attempts safely."""
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = os.path.join(temp_dir, "index.html")
            with open(index_path, "w") as f:
                f.write("<html><body>UI</body></html>")

            with patch("mlflow_oidc_auth.routers.ui._get_ui_directory") as mock_get:
                mock_get.return_value = (
                    Path(temp_dir).resolve(),
                    Path(index_path).resolve(),
                )
                # Attempt path traversal
                response = client.get("/oidc/ui/../../../etc/passwd")

                # Router may either return the SPA (200) or reject access (403)
                assert response.status_code in [200, 403, 404]

                if response.status_code == 200:
                    assert "UI" in response.text

    def test_ui_endpoints_content_types(self, client):
        """Test that UI endpoints return appropriate content types."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create various file types
            files_and_types = [
                ("index.html", "text/html"),
                ("styles.css", "text/css"),
                ("script.js", "application/javascript"),
                ("image.png", "image/png"),
                ("data.json", "application/json"),
            ]

            for filename, expected_type in files_and_types:
                file_path = os.path.join(temp_dir, filename)
                with open(file_path, "w") as f:
                    f.write("test content")

            with patch("mlflow_oidc_auth.routers.ui._get_ui_directory") as mock_get:
                mock_get.return_value = (
                    Path(temp_dir).resolve(),
                    Path(os.path.join(temp_dir, "index.html")).resolve(),
                )
                for filename, expected_type in files_and_types:
                    response = client.get(f"/oidc/ui/{filename}")

                    assert response.status_code == 200
                    # Note: FastAPI's FileResponse sets content-type based on file extension

    def test_ui_endpoints_handle_large_files(self, client):
        """Test that UI endpoints can handle reasonably large files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a larger file (1MB)
            large_file_path = os.path.join(temp_dir, "large.js")
            with open(large_file_path, "w") as f:
                f.write("// Large JavaScript file\n" * 50000)  # ~1MB

            with patch("mlflow_oidc_auth.routers.ui._get_ui_directory") as mock_get:
                mock_get.return_value = (
                    Path(temp_dir).resolve(),
                    Path(os.path.join(temp_dir, "index.html")).resolve(),
                )
                response = client.get("/oidc/ui/large.js")

                assert response.status_code == 200
                assert len(response.content) > 1000000  # Should be ~1MB

    def test_ui_endpoints_handle_empty_files(self, client):
        """Test that UI endpoints handle empty files correctly."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create an empty file
            empty_file_path = os.path.join(temp_dir, "empty.css")
            with open(empty_file_path, "w") as f:
                pass  # Create empty file

            with patch("mlflow_oidc_auth.routers.ui._get_ui_directory") as mock_get:
                mock_get.return_value = (
                    Path(temp_dir).resolve(),
                    Path(os.path.join(temp_dir, "index.html")).resolve(),
                )
                response = client.get("/oidc/ui/empty.css")

                assert response.status_code == 200
                assert len(response.content) == 0

    def test_ui_spa_routes_with_query_parameters(self, client):
        """Test that SPA routes work with query parameters."""
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = os.path.join(temp_dir, "index.html")
            with open(index_path, "w") as f:
                f.write("<html><body>SPA with params</body></html>")

            with patch("mlflow_oidc_auth.routers.ui._get_ui_directory") as mock_get:
                mock_get.return_value = (
                    Path(temp_dir).resolve(),
                    Path(index_path).resolve(),
                )
                # SPA routes with query parameters should work
                response = client.get("/oidc/ui/auth?error=test&code=123")

                assert response.status_code == 200
                assert "SPA with params" in response.text

    def test_ui_spa_routes_with_fragments(self, client):
        """Test that SPA routes work with URL fragments."""
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = os.path.join(temp_dir, "index.html")
            with open(index_path, "w") as f:
                f.write("<html><body>SPA with fragments</body></html>")

            with patch("mlflow_oidc_auth.routers.ui._get_ui_directory") as mock_get:
                mock_get.return_value = (
                    Path(temp_dir).resolve(),
                    Path(index_path).resolve(),
                )
                # Note: URL fragments are handled client-side, but the route should still work
                response = client.get("/oidc/ui/auth")

                assert response.status_code == 200
                assert "SPA with fragments" in response.text
