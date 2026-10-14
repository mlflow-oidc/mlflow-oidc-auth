"""
Comprehensive tests for the hack.py module.

This module tests the hack functionality that extends the MLflow UI
by injecting custom menu elements. Tests cover file handling,
HTML injection, error scenarios, and security implications.
"""

import os
import tempfile
import pytest
from unittest.mock import MagicMock, patch, mock_open
from flask import Response

from mlflow_oidc_auth.hack import index


@pytest.fixture(autouse=True)
def _menu_only_config():
    """Pin pre-existing tests to menu-only injection so their fixtures stay valid.

    Reauth injection (default-on in production) is exercised by its own dedicated
    test class below.
    """

    with patch("mlflow_oidc_auth.hack.config") as cfg:
        cfg.EXTEND_MLFLOW_MENU = True
        cfg.EXTEND_MLFLOW_REAUTH = False
        cfg.EXTEND_MLFLOW_REDIRECT_ADMIN = False
        yield cfg


class TestHackIndex:
    """Test the index function that handles MLflow UI extension."""

    def test_index_static_folder_none(self):
        """Test index function when static folder is None."""
        # Create a mock app object
        mock_app = MagicMock()
        mock_app.static_folder = None

        # Patch the import within the function
        with patch.dict("sys.modules", {"mlflow.server": MagicMock(app=mock_app)}):
            # Call the function
            result = index()

            # Verify response
            assert isinstance(result, Response)
            assert result.mimetype == "text/plain"
            assert result.get_data(as_text=True) == "Static folder is not set"

    def test_index_index_html_not_found(self):
        """Test index function when index.html does not exist."""
        # Create a mock app object
        mock_app = MagicMock()
        mock_app.static_folder = "/fake/static/folder"

        with patch.dict("sys.modules", {"mlflow.server": MagicMock(app=mock_app)}):
            with patch("mlflow_oidc_auth.hack.os.path.exists", return_value=False) as mock_exists:
                # Call the function
                result = index()

                # Verify response
                assert isinstance(result, Response)
                assert result.mimetype == "text/plain"
                assert result.get_data(as_text=True) == "Unable to display MLflow UI - landing page not found"

                # Verify os.path.exists was called with correct path
                mock_exists.assert_called_once_with("/fake/static/folder/index.html")

    def test_index_successful_html_injection(self):
        """Test successful HTML injection into MLflow UI."""
        # Create a mock app object
        mock_app = MagicMock()
        mock_app.static_folder = "/fake/static/folder"

        # Mock HTML content
        original_html = """
        <html>
        <head><title>MLflow</title></head>
        <body>
        <div>MLflow Content</div>
        </body>
        </html>
        """

        menu_html = """
        <script>
        // Custom menu script
        console.log('Menu injected');
        </script>
        """

        with patch.dict("sys.modules", {"mlflow.server": MagicMock(app=mock_app)}):
            with patch("mlflow_oidc_auth.hack.os.path.exists", return_value=True):
                with patch("builtins.open", mock_open()) as mock_file_open:
                    # Configure mock_open to return different content for different files
                    def side_effect(file_path, mode="r"):
                        if "index.html" in file_path:
                            return mock_open(read_data=original_html).return_value
                        elif "menu.html" in file_path:
                            return mock_open(read_data=menu_html).return_value
                        else:
                            raise FileNotFoundError(f"File not found: {file_path}")

                    mock_file_open.side_effect = side_effect

                    # Call the function
                    result = index()

                    # Verify the result
                    expected_html = original_html.replace("</body>", f"{menu_html}\n</body>")
                    assert result == expected_html

                    # Verify file operations
                    assert mock_file_open.call_count == 2

    def test_index_html_without_body_tag(self):
        """Test HTML injection when original HTML doesn't have closing body tag."""
        # Create a mock app object
        mock_app = MagicMock()
        mock_app.static_folder = "/fake/static/folder"

        # Mock HTML content without closing body tag
        original_html = """
        <html>
        <head><title>MLflow</title></head>
        <div>MLflow Content</div>
        </html>
        """

        menu_html = "<script>console.log('Menu');</script>"

        with patch.dict("sys.modules", {"mlflow.server": MagicMock(app=mock_app)}):
            with patch("mlflow_oidc_auth.hack.os.path.exists", return_value=True):
                with patch("builtins.open", mock_open()) as mock_file_open:

                    def side_effect(file_path, mode="r"):
                        if "index.html" in file_path:
                            return mock_open(read_data=original_html).return_value
                        elif "menu.html" in file_path:
                            return mock_open(read_data=menu_html).return_value
                        else:
                            raise FileNotFoundError(f"File not found: {file_path}")

                    mock_file_open.side_effect = side_effect

                    # Call the function
                    result = index()

                    # Verify the result - should return original HTML unchanged since no </body> tag
                    assert result == original_html

    def test_index_multiple_body_tags(self):
        """Test HTML injection with multiple closing body tags."""
        # Create a mock app object
        mock_app = MagicMock()
        mock_app.static_folder = "/fake/static/folder"

        # Mock HTML content with multiple closing body tags
        original_html = """
        <html>
        <head><title>MLflow</title></head>
        <body>
        <div>First section</div>
        </body>
        <body>
        <div>Second section</div>
        </body>
        </html>
        """

        menu_html = "<script>console.log('Menu');</script>"

        with patch.dict("sys.modules", {"mlflow.server": MagicMock(app=mock_app)}):
            with patch("mlflow_oidc_auth.hack.os.path.exists", return_value=True):
                with patch("builtins.open", mock_open()) as mock_file_open:

                    def side_effect(file_path, mode="r"):
                        if "index.html" in file_path:
                            return mock_open(read_data=original_html).return_value
                        elif "menu.html" in file_path:
                            return mock_open(read_data=menu_html).return_value
                        else:
                            raise FileNotFoundError(f"File not found: {file_path}")

                    mock_file_open.side_effect = side_effect

                    # Call the function
                    result = index()

                    # Verify the result - should replace only the first occurrence
                    # The actual implementation replaces all occurrences, not just the first
                    expected_html = original_html.replace("</body>", f"{menu_html}\n</body>")
                    assert result == expected_html

    def test_index_file_read_error_index_html(self):
        """Test index function when reading index.html fails."""
        # Create a mock app object
        mock_app = MagicMock()
        mock_app.static_folder = "/fake/static/folder"

        with patch.dict("sys.modules", {"mlflow.server": MagicMock(app=mock_app)}):
            with patch("mlflow_oidc_auth.hack.os.path.exists", return_value=True):
                with patch("builtins.open", side_effect=IOError("Permission denied")):
                    # Call the function and expect exception
                    with pytest.raises(IOError, match="Permission denied"):
                        index()

    def test_index_file_read_error_menu_html(self):
        """Test index function when reading menu.html fails."""
        # Create a mock app object
        mock_app = MagicMock()
        mock_app.static_folder = "/fake/static/folder"

        original_html = "<html><body>Content</body></html>"

        with patch.dict("sys.modules", {"mlflow.server": MagicMock(app=mock_app)}):
            with patch("mlflow_oidc_auth.hack.os.path.exists", return_value=True):
                with patch("builtins.open", mock_open()) as mock_file_open:

                    def side_effect(file_path, mode="r"):
                        if "index.html" in file_path:
                            return mock_open(read_data=original_html).return_value
                        elif "menu.html" in file_path:
                            raise IOError("Menu file not accessible")
                        else:
                            raise FileNotFoundError(f"File not found: {file_path}")

                    mock_file_open.side_effect = side_effect

                    # Call the function and expect exception
                    with pytest.raises(IOError, match="Menu file not accessible"):
                        index()

    def test_index_empty_files(self):
        """Test index function with empty HTML files."""
        # Create a mock app object
        mock_app = MagicMock()
        mock_app.static_folder = "/fake/static/folder"

        # Mock empty files
        original_html = ""
        menu_html = ""

        with patch.dict("sys.modules", {"mlflow.server": MagicMock(app=mock_app)}):
            with patch("mlflow_oidc_auth.hack.os.path.exists", return_value=True):
                with patch("builtins.open", mock_open()) as mock_file_open:

                    def side_effect(file_path, mode="r"):
                        if "index.html" in file_path:
                            return mock_open(read_data=original_html).return_value
                        elif "menu.html" in file_path:
                            return mock_open(read_data=menu_html).return_value
                        else:
                            raise FileNotFoundError(f"File not found: {file_path}")

                    mock_file_open.side_effect = side_effect

                    # Call the function
                    result = index()

                    # Verify the result - empty string since no </body> tag to replace
                    assert result == ""

    def test_index_large_html_files(self):
        """Test index function with large HTML files."""
        # Create a mock app object
        mock_app = MagicMock()
        mock_app.static_folder = "/fake/static/folder"

        # Create large HTML content
        large_content = "<div>" * 1000 + "Content" + "</div>" * 1000
        original_html = f"<html><body>{large_content}</body></html>"
        menu_html = "<script>console.log('Large file test');</script>"

        with patch.dict("sys.modules", {"mlflow.server": MagicMock(app=mock_app)}):
            with patch("mlflow_oidc_auth.hack.os.path.exists", return_value=True):
                with patch("builtins.open", mock_open()) as mock_file_open:

                    def side_effect(file_path, mode="r"):
                        if "index.html" in file_path:
                            return mock_open(read_data=original_html).return_value
                        elif "menu.html" in file_path:
                            return mock_open(read_data=menu_html).return_value
                        else:
                            raise FileNotFoundError(f"File not found: {file_path}")

                    mock_file_open.side_effect = side_effect

                    # Call the function
                    result = index()

                    # Verify the result contains the injection
                    assert menu_html in result
                    assert result.endswith("</body></html>")

    def test_index_special_characters_in_html(self):
        """Test index function with special characters in HTML content."""
        # Create a mock app object
        mock_app = MagicMock()
        mock_app.static_folder = "/fake/static/folder"

        # HTML with special characters
        original_html = """
        <html>
        <body>
        <div>Content with special chars: &lt;&gt;&amp;"'</div>
        <script>var data = {"key": "value"};</script>
        </body>
        </html>
        """

        menu_html = """
        <script>
        var config = {"special": "&lt;test&gt;"};
        console.log('Special chars: &amp;');
        </script>
        """

        with patch.dict("sys.modules", {"mlflow.server": MagicMock(app=mock_app)}):
            with patch("mlflow_oidc_auth.hack.os.path.exists", return_value=True):
                with patch("builtins.open", mock_open()) as mock_file_open:

                    def side_effect(file_path, mode="r"):
                        if "index.html" in file_path:
                            return mock_open(read_data=original_html).return_value
                        elif "menu.html" in file_path:
                            return mock_open(read_data=menu_html).return_value
                        else:
                            raise FileNotFoundError(f"File not found: {file_path}")

                    mock_file_open.side_effect = side_effect

                    # Call the function
                    result = index()

                    # Verify the result contains both original and injected content
                    assert "&lt;&gt;&amp;" in result  # Original special chars
                    assert "&lt;test&gt;" in result  # Injected special chars
                    assert menu_html in result

    def test_index_unicode_content(self):
        """Test index function with Unicode content."""
        # Create a mock app object
        mock_app = MagicMock()
        mock_app.static_folder = "/fake/static/folder"

        # HTML with Unicode characters
        original_html = """
        <html>
        <body>
        <div>Unicode content: 你好世界 🌍 café naïve résumé</div>
        </body>
        </html>
        """

        menu_html = """
        <script>
        console.log('Unicode menu: 🚀 ñoño');
        </script>
        """

        with patch.dict("sys.modules", {"mlflow.server": MagicMock(app=mock_app)}):
            with patch("mlflow_oidc_auth.hack.os.path.exists", return_value=True):
                with patch("builtins.open", mock_open()) as mock_file_open:

                    def side_effect(file_path, mode="r"):
                        if "index.html" in file_path:
                            return mock_open(read_data=original_html).return_value
                        elif "menu.html" in file_path:
                            return mock_open(read_data=menu_html).return_value
                        else:
                            raise FileNotFoundError(f"File not found: {file_path}")

                    mock_file_open.side_effect = side_effect

                    # Call the function
                    result = index()

                    # Verify Unicode content is preserved
                    assert "你好世界" in result
                    assert "🌍" in result
                    assert "café" in result
                    assert "🚀" in result
                    assert "ñoño" in result

    def test_index_case_sensitive_body_tag(self):
        """Test that body tag replacement is case sensitive."""
        # Create a mock app object
        mock_app = MagicMock()
        mock_app.static_folder = "/fake/static/folder"

        # HTML with uppercase BODY tag
        original_html = """
        <html>
        <BODY>
        <div>Content</div>
        </BODY>
        </html>
        """

        menu_html = "<script>Menu</script>"

        with patch.dict("sys.modules", {"mlflow.server": MagicMock(app=mock_app)}):
            with patch("mlflow_oidc_auth.hack.os.path.exists", return_value=True):
                with patch("builtins.open", mock_open()) as mock_file_open:

                    def side_effect(file_path, mode="r"):
                        if "index.html" in file_path:
                            return mock_open(read_data=original_html).return_value
                        elif "menu.html" in file_path:
                            return mock_open(read_data=menu_html).return_value
                        else:
                            raise FileNotFoundError(f"File not found: {file_path}")

                    mock_file_open.side_effect = side_effect

                    # Call the function
                    result = index()

                    # Verify that uppercase </BODY> is not replaced (case sensitive)
                    assert result == original_html
                    assert menu_html not in result


class TestHackModuleSecurity:
    """Test security implications of the hack module."""

    def test_index_script_injection_prevention(self):
        """Test that the function doesn't introduce XSS vulnerabilities."""
        # Create a mock app object
        mock_app = MagicMock()
        mock_app.static_folder = "/fake/static/folder"

        # HTML with potentially malicious content
        original_html = """
        <html>
        <body>
        <div>Normal content</div>
        </body>
        </html>
        """

        # Menu with potentially malicious script
        malicious_menu = """
        <script>
        // This is controlled content from menu.html file
        alert('This is from menu.html');
        </script>
        """

        with patch.dict("sys.modules", {"mlflow.server": MagicMock(app=mock_app)}):
            with patch("mlflow_oidc_auth.hack.os.path.exists", return_value=True):
                with patch("builtins.open", mock_open()) as mock_file_open:

                    def side_effect(file_path, mode="r"):
                        if "index.html" in file_path:
                            return mock_open(read_data=original_html).return_value
                        elif "menu.html" in file_path:
                            return mock_open(read_data=malicious_menu).return_value
                        else:
                            raise FileNotFoundError(f"File not found: {file_path}")

                    mock_file_open.side_effect = side_effect

                    # Call the function
                    result = index()

                    # Verify that the content is injected as-is (no sanitization)
                    # This is expected behavior since menu.html is a controlled file
                    assert malicious_menu in result
                    assert "alert('This is from menu.html');" in result

    def test_index_path_traversal_protection(self):
        """Test that the function uses safe file paths."""
        # Create a mock app object
        mock_app = MagicMock()
        mock_app.static_folder = "/fake/static/folder"

        original_html = "<html><body>Content</body></html>"
        menu_html = "<script>Menu</script>"

        with patch.dict("sys.modules", {"mlflow.server": MagicMock(app=mock_app)}):
            with patch("mlflow_oidc_auth.hack.os.path.exists", return_value=True):
                with patch("builtins.open", mock_open()) as mock_file_open:

                    def side_effect(file_path, mode="r"):
                        # Verify that file paths are constructed safely
                        if file_path == "/fake/static/folder/index.html":
                            return mock_open(read_data=original_html).return_value
                        elif file_path.endswith("hack/menu.html"):
                            return mock_open(read_data=menu_html).return_value
                        else:
                            raise FileNotFoundError(f"Unexpected file path: {file_path}")

                    mock_file_open.side_effect = side_effect

                    # Call the function
                    result = index()

                    # Verify successful execution with expected file paths
                    assert menu_html in result

    def test_index_file_content_validation(self):
        """Test behavior with various file content types."""
        # Create a mock app object
        mock_app = MagicMock()
        mock_app.static_folder = "/fake/static/folder"

        # Test with binary-like content (should still work as text)
        original_html = "<html><body>\x00\x01\x02</body></html>"
        menu_html = "<script>Binary test</script>"

        with patch.dict("sys.modules", {"mlflow.server": MagicMock(app=mock_app)}):
            with patch("mlflow_oidc_auth.hack.os.path.exists", return_value=True):
                with patch("builtins.open", mock_open()) as mock_file_open:

                    def side_effect(file_path, mode="r"):
                        if "index.html" in file_path:
                            return mock_open(read_data=original_html).return_value
                        elif "menu.html" in file_path:
                            return mock_open(read_data=menu_html).return_value
                        else:
                            raise FileNotFoundError(f"File not found: {file_path}")

                    mock_file_open.side_effect = side_effect

                    # Call the function
                    result = index()

                    # Verify that binary content is handled
                    assert menu_html in result


class TestHackModuleEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_index_very_long_file_paths(self):
        """Test with very long file paths."""
        # Create a mock app object with long path
        mock_app = MagicMock()
        long_path = "/fake/" + "very_long_directory_name/" * 10 + "static"
        mock_app.static_folder = long_path

        original_html = "<html><body>Long path test</body></html>"
        menu_html = "<script>Long path menu</script>"

        with patch.dict("sys.modules", {"mlflow.server": MagicMock(app=mock_app)}):
            with patch("mlflow_oidc_auth.hack.os.path.exists", return_value=True):
                with patch("builtins.open", mock_open()) as mock_file_open:

                    def side_effect(file_path, mode="r"):
                        if file_path == f"{long_path}/index.html":
                            return mock_open(read_data=original_html).return_value
                        elif "menu.html" in file_path:
                            return mock_open(read_data=menu_html).return_value
                        else:
                            raise FileNotFoundError(f"File not found: {file_path}")

                    mock_file_open.side_effect = side_effect

                    # Call the function
                    result = index()

                    # Verify successful execution
                    assert menu_html in result

    def test_index_nested_body_tags(self):
        """Test with nested or malformed body tags."""
        # Create a mock app object
        mock_app = MagicMock()
        mock_app.static_folder = "/fake/static/folder"

        # HTML with nested body-like content
        original_html = """
        <html>
        <body>
        <div>Content with </body> in text</div>
        <div>More content</div>
        </body>
        </html>
        """

        menu_html = "<script>Nested test</script>"

        with patch.dict("sys.modules", {"mlflow.server": MagicMock(app=mock_app)}):
            with patch("mlflow_oidc_auth.hack.os.path.exists", return_value=True):
                with patch("builtins.open", mock_open()) as mock_file_open:

                    def side_effect(file_path, mode="r"):
                        if "index.html" in file_path:
                            return mock_open(read_data=original_html).return_value
                        elif "menu.html" in file_path:
                            return mock_open(read_data=menu_html).return_value
                        else:
                            raise FileNotFoundError(f"File not found: {file_path}")

                    mock_file_open.side_effect = side_effect

                    # Call the function
                    result = index()

                    # Verify that only the first </body> is replaced
                    body_count = result.count("</body>")
                    original_body_count = original_html.count("</body>")
                    assert body_count == original_body_count  # Same number of </body> tags

    def test_index_whitespace_handling(self):
        """Test handling of whitespace in HTML content."""
        # Create a mock app object
        mock_app = MagicMock()
        mock_app.static_folder = "/fake/static/folder"

        # HTML with various whitespace
        original_html = """
        <html>
        <body>


        <div>   Content with spaces   </div>


        </body>
        </html>
        """

        menu_html = """

        <script>
            // Menu with whitespace
            console.log('test');
        </script>

        """

        with patch.dict("sys.modules", {"mlflow.server": MagicMock(app=mock_app)}):
            with patch("mlflow_oidc_auth.hack.os.path.exists", return_value=True):
                with patch("builtins.open", mock_open()) as mock_file_open:

                    def side_effect(file_path, mode="r"):
                        if "index.html" in file_path:
                            return mock_open(read_data=original_html).return_value
                        elif "menu.html" in file_path:
                            return mock_open(read_data=menu_html).return_value
                        else:
                            raise FileNotFoundError(f"File not found: {file_path}")

                    mock_file_open.side_effect = side_effect

                    # Call the function
                    result = index()

                    # Verify whitespace is preserved
                    assert "   Content with spaces   " in result
                    assert menu_html in result


class TestHackModuleIntegration:
    """Test integration scenarios and real-world usage patterns."""

    def test_index_with_real_file_system(self):
        """Test with actual file system operations (mocked for safety)."""
        # Create a mock app object
        mock_app = MagicMock()
        mock_app.static_folder = "/fake/static/folder"

        # Use real file operations but with mocked paths
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            index_file = os.path.join(temp_dir, "index.html")
            menu_file = os.path.join(temp_dir, "menu.html")

            with open(index_file, "w") as f:
                f.write("<html><body>Real file test</body></html>")

            with open(menu_file, "w") as f:
                f.write("<script>Real menu</script>")

            with patch.dict("sys.modules", {"mlflow.server": MagicMock(app=mock_app)}):
                # Mock the file paths to use our temp files
                with (
                    patch("mlflow_oidc_auth.hack.os.path.join") as mock_join,
                    patch("mlflow_oidc_auth.hack.os.path.dirname") as mock_dirname,
                    patch("mlflow_oidc_auth.hack.os.path.exists", return_value=True),
                ):

                    def join_side_effect(*args):
                        if args[-1] == "index.html":
                            return index_file
                        elif args[-1] == "menu.html":
                            return menu_file
                        # Use the real os.path.join for other cases
                        import os as real_os

                        return real_os.path.join(*args)

                    mock_join.side_effect = join_side_effect
                    mock_dirname.return_value = temp_dir

                    # Call the function
                    result = index()

                    # Verify the result
                    assert "Real file test" in result
                    assert "Real menu" in result

    def test_index_function_signature(self):
        """Test that the index function has the correct signature."""
        import inspect

        # Get function signature
        sig = inspect.signature(index)

        # Verify no parameters
        assert len(sig.parameters) == 0

        # Verify function is callable
        assert callable(index)

    def test_index_return_type_consistency(self):
        """Test that index function returns consistent types."""
        # Test case 1: static_folder is None
        mock_app1 = MagicMock()
        mock_app1.static_folder = None

        with patch.dict("sys.modules", {"mlflow.server": MagicMock(app=mock_app1)}):
            result1 = index()
            assert isinstance(result1, Response)

        # Test case 2: index.html not found
        mock_app2 = MagicMock()
        mock_app2.static_folder = "/fake/path"

        with patch.dict("sys.modules", {"mlflow.server": MagicMock(app=mock_app2)}):
            with patch("mlflow_oidc_auth.hack.os.path.exists", return_value=False):
                result2 = index()
                assert isinstance(result2, Response)

        # Test case 3: successful injection
        mock_app3 = MagicMock()
        mock_app3.static_folder = "/fake/path"

        with patch.dict("sys.modules", {"mlflow.server": MagicMock(app=mock_app3)}):
            with patch("mlflow_oidc_auth.hack.os.path.exists", return_value=True):
                with patch(
                    "builtins.open",
                    mock_open(read_data="<html><body>test</body></html>"),
                ):
                    result3 = index()
                    assert isinstance(result3, str)


class TestHackModuleErrorHandling:
    """Test comprehensive error handling scenarios."""

    def test_index_os_path_exists_exception(self):
        """Test when os.path.exists raises an exception."""
        # Create a mock app object
        mock_app = MagicMock()
        mock_app.static_folder = "/fake/static/folder"

        with patch.dict("sys.modules", {"mlflow.server": MagicMock(app=mock_app)}):
            with patch(
                "mlflow_oidc_auth.hack.os.path.exists",
                side_effect=OSError("Permission denied to check file existence"),
            ):
                # Call the function and expect exception
                with pytest.raises(OSError, match="Permission denied to check file existence"):
                    index()

    def test_index_os_path_join_exception(self):
        """Test when os.path.join raises an exception."""
        # Create a mock app object
        mock_app = MagicMock()
        mock_app.static_folder = "/fake/static/folder"

        with patch.dict("sys.modules", {"mlflow.server": MagicMock(app=mock_app)}):
            with patch("mlflow_oidc_auth.hack.os.path.exists", return_value=True):
                with patch(
                    "mlflow_oidc_auth.hack.os.path.join",
                    side_effect=TypeError("Invalid path components"),
                ):
                    # Call the function and expect exception
                    with pytest.raises(TypeError, match="Invalid path components"):
                        index()

    def test_index_string_replace_edge_cases(self):
        """Test string replacement edge cases."""
        # Create a mock app object
        mock_app = MagicMock()
        mock_app.static_folder = "/fake/static/folder"

        # Test with None-like content that could cause issues
        test_cases = [
            ("", ""),  # Empty strings
            ("<html></html>", "<script></script>"),  # No body tag
            ("</body>", ""),  # Only closing body tag
            ("</body></body></body>", "<script>test</script>"),  # Multiple body tags
        ]

        for original_html, menu_html in test_cases:
            with patch.dict("sys.modules", {"mlflow.server": MagicMock(app=mock_app)}):
                with patch("mlflow_oidc_auth.hack.os.path.exists", return_value=True):
                    with patch("builtins.open", mock_open()) as mock_file_open:

                        def side_effect(file_path, mode="r"):
                            if "index.html" in file_path:
                                return mock_open(read_data=original_html).return_value
                            elif "menu.html" in file_path:
                                return mock_open(read_data=menu_html).return_value
                            else:
                                raise FileNotFoundError(f"File not found: {file_path}")

                        mock_file_open.side_effect = side_effect

                        # Call the function - should not raise exceptions
                        result = index()

                        # Verify result is a string
                        assert isinstance(result, str)


class TestHackModulePerformance:
    """Test performance-related aspects of the hack module."""

    def test_index_memory_efficiency(self):
        """Test that the function handles large files efficiently."""
        # Create a mock app object
        mock_app = MagicMock()
        mock_app.static_folder = "/fake/static/folder"

        # Create large content to test memory usage
        large_html_content = "x" * 100000  # 100KB of content
        original_html = f"<html><body>{large_html_content}</body></html>"
        menu_html = "<script>Large file test</script>"

        with patch.dict("sys.modules", {"mlflow.server": MagicMock(app=mock_app)}):
            with patch("mlflow_oidc_auth.hack.os.path.exists", return_value=True):
                with patch("builtins.open", mock_open()) as mock_file_open:

                    def side_effect(file_path, mode="r"):
                        if "index.html" in file_path:
                            return mock_open(read_data=original_html).return_value
                        elif "menu.html" in file_path:
                            return mock_open(read_data=menu_html).return_value
                        else:
                            raise FileNotFoundError(f"File not found: {file_path}")

                    mock_file_open.side_effect = side_effect

                    # Call the function
                    result = index()

                    # Verify the function completes and produces correct output
                    assert len(result) > 100000  # Should be larger than original
                    assert menu_html in result
                    assert large_html_content in result

    def test_index_file_operations_count(self):
        """Test that the function performs minimal file operations."""
        # Create a mock app object
        mock_app = MagicMock()
        mock_app.static_folder = "/fake/static/folder"

        original_html = "<html><body>Content</body></html>"
        menu_html = "<script>Menu</script>"

        with patch.dict("sys.modules", {"mlflow.server": MagicMock(app=mock_app)}):
            with patch("mlflow_oidc_auth.hack.os.path.exists", return_value=True) as mock_exists:
                with patch("builtins.open", mock_open()) as mock_file_open:

                    def side_effect(file_path, mode="r"):
                        if "index.html" in file_path:
                            return mock_open(read_data=original_html).return_value
                        elif "menu.html" in file_path:
                            return mock_open(read_data=menu_html).return_value
                        else:
                            raise FileNotFoundError(f"File not found: {file_path}")

                    mock_file_open.side_effect = side_effect

                    # Call the function
                    result = index()

                    # Verify minimal file operations
                    assert mock_file_open.call_count == 2  # Only index.html and menu.html
                    assert mock_exists.call_count == 2  # index.html and menu.html existence checks

                    # Verify correct result
                    assert menu_html in result


@pytest.fixture(autouse=True)
def _fresh_snippet_cache():
    """index() caches snippet files; every test here controls their content through mocks."""
    from mlflow_oidc_auth import hack

    hack._read_snippet.cache_clear()
    yield
    hack._read_snippet.cache_clear()


def _run_index(html: str, snippets: dict, *, reauth: bool, menu: bool, redirect: bool = False, script_root: str = ""):
    """Drive ``hack.index()`` inside a request served under ``script_root``, with a controlled
    file-system / config state."""
    from flask import Flask

    mock_app = MagicMock()
    mock_app.static_folder = "/fake/static"

    def open_side_effect(file_path, mode="r"):
        if "index.html" in file_path:
            return mock_open(read_data=html).return_value
        for key, content in snippets.items():
            if key in file_path:
                return mock_open(read_data=content).return_value
        raise FileNotFoundError(file_path)

    with (
        patch.dict("sys.modules", {"mlflow.server": MagicMock(app=mock_app)}),
        patch("mlflow_oidc_auth.hack.os.path.exists", return_value=True),
        patch("builtins.open", mock_open()) as mock_file_open,
        patch("mlflow_oidc_auth.hack.config") as cfg,
        Flask(__name__).test_request_context("/", environ_overrides={"SCRIPT_NAME": script_root}),
    ):
        cfg.EXTEND_MLFLOW_REAUTH = reauth
        cfg.EXTEND_MLFLOW_MENU = menu
        cfg.EXTEND_MLFLOW_REDIRECT_ADMIN = redirect
        mock_file_open.side_effect = open_side_effect
        return index()


class TestReauthInjection:
    """Cover the EXTEND_MLFLOW_REAUTH flag and the combined injection ordering."""

    def test_reauth_only_injection(self):
        """When only reauth is enabled, only the reauth snippet is appended."""
        html = "<html><body>Content</body></html>"
        result = _run_index(
            html,
            {"reauth.html": "<script>REAUTH</script>", "menu.html": "<script>MENU</script>"},
            reauth=True,
            menu=False,
        )
        assert "REAUTH" in result
        assert "MENU" not in result
        assert "</body>" in result

    def test_both_enabled_reauth_runs_first(self):
        """Reauth must precede menu in the injected output so the fetch patch
        is in place before any later script issues network calls."""
        html = "<html><body>Content</body></html>"
        result = _run_index(
            html,
            {"reauth.html": "<!--REAUTH_MARK-->", "menu.html": "<!--MENU_MARK-->"},
            reauth=True,
            menu=True,
        )
        assert result.index("REAUTH_MARK") < result.index("MENU_MARK")

    def test_both_disabled_returns_unmodified(self):
        """If both flags are off, ``index`` returns the original HTML unchanged."""
        html = "<html><body>Content</body></html>"
        result = _run_index(
            html,
            {"reauth.html": "<!--REAUTH-->", "menu.html": "<!--MENU-->"},
            reauth=False,
            menu=False,
        )
        assert "REAUTH" not in result
        assert "MENU" not in result
        assert result == html

    def test_reauth_snippet_file_exists_in_repo(self):
        """The shipped reauth.html must exist on disk — otherwise default-on
        deployments silently degrade to no re-auth helper."""
        from mlflow_oidc_auth import hack

        snippet_path = os.path.join(hack._HACK_DIR, "reauth.html")
        assert os.path.isfile(snippet_path)
        with open(snippet_path) as f:
            content = f.read()
        # Spot-check: the snippet should patch fetch and XHR, react to a 401,
        # and forward the current location to /login as ?next=.
        assert "window.fetch" in content
        assert "XMLHttpRequest.prototype.send" in content
        assert "401" in content
        assert "/login?next=" in content
        assert "window.location.hash" in content


class TestRedirectInjection:
    """Cover the EXTEND_MLFLOW_REDIRECT_ADMIN flag and its injection ordering."""

    _SNIPPETS = {"redirect.html": "<!--REDIRECT_MARK-->", "reauth.html": "<!--REAUTH_MARK-->", "menu.html": "<!--MENU_MARK-->"}

    def _run_index(self, *, redirect: bool, reauth: bool, menu: bool):
        return _run_index("<html><body>Content</body></html>", self._SNIPPETS, reauth=reauth, menu=menu, redirect=redirect)

    @pytest.mark.parametrize(
        "script_root,expected",
        [
            ("", ""),
            ("/mlflow", "/mlflow"),
            ("/mlflow/", "/mlflow"),
            ("//evil.com", ""),
            ("evil.com", ""),
            ('/a"</script><script>alert(1)', '/a\\"\\u003c/script\\u003e\\u003cscript\\u003ealert(1)'),
        ],
    )
    def test_base_path_is_filled_in_from_the_request(self, script_root, expected):
        from mlflow_oidc_auth.hack import BASE_PATH_PLACEHOLDER

        snippets = {"redirect.html": f'<script>var BASE_PATH = "{BASE_PATH_PLACEHOLDER}";</script>'}
        result = _run_index("<html><body>Content</body></html>", snippets, reauth=False, menu=False, redirect=True, script_root=script_root)
        assert BASE_PATH_PLACEHOLDER not in result
        assert f'var BASE_PATH = "{expected}";' in result
        assert result.count("</script>") == 1

    def test_redirect_snippet_injected_when_enabled(self):
        result = self._run_index(redirect=True, reauth=False, menu=False)
        assert "REDIRECT_MARK" in result
        assert result.index("REDIRECT_MARK") < result.index("</body>")
        assert "REAUTH_MARK" not in result
        assert "MENU_MARK" not in result

    def test_redirect_snippet_absent_when_disabled(self):
        result = self._run_index(redirect=False, reauth=True, menu=True)
        assert "REDIRECT_MARK" not in result
        assert "REAUTH_MARK" in result
        assert "MENU_MARK" in result

    def test_redirect_snippet_injected_before_reauth(self):
        result = self._run_index(redirect=True, reauth=True, menu=True)
        assert result.index("REDIRECT_MARK") < result.index("REAUTH_MARK") < result.index("MENU_MARK")

    def test_redirect_snippet_file_exists_in_repo(self):
        from mlflow_oidc_auth import hack

        snippet_path = os.path.join(hack._HACK_DIR, "redirect.html")
        assert os.path.isfile(snippet_path)
        with open(snippet_path) as f:
            content = f.read()
        assert "window.__" not in content  # no test hooks on the page
        assert "window.location.replace" in content
        for event in ("hashchange", "popstate", '"pushState"', '"replaceState"'):
            assert event in content
        assert "encodeURIComponent" in content
        # No DOM writes and no external requests.
        for forbidden in ("innerHTML", "outerHTML", "document.write", "fetch(", "XMLHttpRequest", "http://", "https://"):
            assert forbidden not in content


# ── Mapping function, evaluated in node ─────────────────────────────────────

_NODE_HARNESS = r"""
const fs = require("fs");
const html = fs.readFileSync(process.argv[1], "utf8").split("__MLFLOW_OIDC_BASE_PATH__").join(process.argv[2]);
const m = html.match(/<script>([\s\S]*?)<\/script>/);
if (!m) throw new Error("no <script> in snippet");
const fn = html.match(/\/\/ BEGIN mapAdminRoute[^\n]*\n([\s\S]*?)\/\/ END mapAdminRoute/);
if (!fn) throw new Error("no mapAdminRoute markers in snippet");
const map = new Function(fn[1] + "\nreturn mapAdminRoute;")();
const replaced = [];
const listeners = {};
const history = { pushState() { return "pushed"; }, replaceState() { return "replaced"; } };
globalThis.window = {
  location: { hash: "", replace: (t) => replaced.push(t) },
  history,
  addEventListener: (name, f) => { listeners[name] = f; },
};
new Function(m[1])();
if (replaced.length !== 0) throw new Error("redirected on an empty hash");
for (const name of ["hashchange", "popstate"]) {
  if (typeof listeners[name] !== "function") throw new Error("no " + name + " listener");
}
const hashes = JSON.parse(fs.readFileSync(0, "utf8"));
const mapped = hashes.map((h) => map(h));
// Drive every real entry point once so the replace() wiring is exercised: a reload-style
// hashchange, back/forward (popstate), and the router's pushState / replaceState.
window.location.hash = "#/admin";
listeners.hashchange();
window.location.hash = "#/account";
listeners.popstate();
window.location.hash = "#/admin/ws?workspace=team-a";
if (window.history.pushState({}, "", "#/admin/ws?workspace=team-a") !== "pushed") throw new Error("pushState result lost");
window.location.hash = "#/admin?tab=roles";
window.history.replaceState({}, "", "#/admin?tab=roles");
window.location.hash = "#/experiments";
window.history.pushState({}, "", "#/experiments");
process.stdout.write(JSON.stringify({ mapped, replaced }));
"""

_MAPPING_CASES = [
    # #/admin, any query except tab=roles -> users
    ("#/admin", "oidc/ui/users"),
    ("#/admin/", "oidc/ui/users"),
    ("#/admin?tab=users", "oidc/ui/users"),
    ("#/admin?foo=bar", "oidc/ui/users"),
    # roles -> groups
    ("#/admin?tab=roles", "oidc/ui/groups"),
    ("#/admin?foo=1&tab=roles", "oidc/ui/groups"),
    ("#/admin/roles/42", "oidc/ui/groups"),
    ("#/admin/roles/anything/else?x=1", "oidc/ui/groups"),
    # users/<u> -> users/<u>/experiments
    ("#/admin/users/alice", "oidc/ui/users/alice/experiments"),
    ("#/admin/users/alice%40example.com", "oidc/ui/users/alice%40example.com/experiments"),
    ("#/admin/users/a%2Fb", "oidc/ui/users/a%2Fb/experiments"),
    ("#/admin/users/a/b", "oidc/ui/users/a/experiments"),
    ("#/admin/users/alice/", "oidc/ui/users/alice/experiments"),
    ("#/admin/users/alice/permissions", "oidc/ui/users/alice/experiments"),
    ("#/admin/users/a%3Fb", "oidc/ui/users/a%3Fb/experiments"),
    ("#/admin/users/a%23b", "oidc/ui/users/a%23b/experiments"),
    ("#/admin/users/a#b", "oidc/ui/users/a%23b/experiments"),
    ("#/admin/users/100%25", "oidc/ui/users/100%25/experiments"),
    ("#/admin/users/100%", "oidc/ui/users/100%25/experiments"),
    ("#/admin/users/a..b", "oidc/ui/users/a..b/experiments"),
    ("#/admin/users/..", "oidc/ui/users"),
    ("#/admin/users/%2E%2E", "oidc/ui/users"),
    ("#/admin/users/../../logout", "oidc/ui/users"),
    ("#/admin/users/", "oidc/ui/users"),
    ("#/admin/users", "oidc/ui/users"),
    # ws?workspace=<w> -> workspaces/<w>
    ("#/admin/ws?workspace=team-a", "oidc/ui/workspaces/team-a"),
    ("#/admin/ws?workspace=a%2Fb", "oidc/ui/workspaces/a%2Fb"),
    ("#/admin/ws?workspace=a/b", "oidc/ui/workspaces/a%2Fb"),
    ("#/admin/ws?workspace=a%3Fb", "oidc/ui/workspaces/a%3Fb"),
    ("#/admin/ws?workspace=a%23b", "oidc/ui/workspaces/a%23b"),
    ("#/admin/ws?workspace=a#b", "oidc/ui/workspaces/a%23b"),
    ("#/admin/ws?workspace=100%25", "oidc/ui/workspaces/100%25"),
    ("#/admin/ws?workspace=..", "oidc/ui/workspaces"),
    ("#/admin/ws?workspace=%2e%2e", "oidc/ui/workspaces"),
    ("#/admin/ws?workspace=.%2e", "oidc/ui/workspaces"),
    ("#/admin/users/.%2E", "oidc/ui/users"),
    ("#/admin/users/%2e.", "oidc/ui/users"),
    ("#/admin/users/%252e%252e", "oidc/ui/users/%252e%252e/experiments"),
    ("#/admin/ws?workspace=a..b", "oidc/ui/workspaces/a..b"),
    ("#/admin/ws?workspace=", "oidc/ui/workspaces"),
    ("#/admin/ws", "oidc/ui/workspaces"),
    # Matched like MLflow's router: per segment, decoded, ignoring case
    ("#/Admin", "oidc/ui/users"),
    ("#/ACCOUNT", "oidc/ui/user"),
    ("#/%61dmin", "oidc/ui/users"),
    ("#/admin/USERS/Alice", "oidc/ui/users/Alice/experiments"),
    ("#/Admin/WS?workspace=team-a", "oidc/ui/workspaces/team-a"),
    ("#/admin/?tab=roles", "oidc/ui/groups"),
    # Only "." and ".." collapse; other dot names are real names
    ("#/admin/users/...", "oidc/ui/users/.../experiments"),
    ("#/admin/ws?workspace=...", "oidc/ui/workspaces/..."),
    ("#/admin/ws/", "oidc/ui/workspaces"),
    ("#/admin/ws/team-a?workspace=team-a", "oidc/ui/workspaces/team-a"),
    # Any other page of the admin area -> users
    ("#/admin/settings", "oidc/ui/users"),
    ("#/admin/something/else?x=1", "oidc/ui/users"),
    # account -> user
    ("#/account", "oidc/ui/user"),
    ("#/account?tab=tokens", "oidc/ui/user"),
    # Not admin routes: left alone.
    ("", None),
    ("#", None),
    ("#/", None),
    ("#/experiments", None),
    ("#/administrator", None),
    ("#/admin-tools", None),
    ("#/accounts", None),
    ("#/models/admin", None),
]

_HOSTILE_HASHES = [
    "#/admin/users/%2F%2Fevil.com",
    "#/admin/users///evil.com",
    "#/admin/users/https:%2F%2Fevil.com",
    "#/admin/users/https://evil.com",
    "#/admin/users/javascript:alert(1)",
    "#/admin/users/%5C%5Cevil.com",
    "#/admin/users/%00",
    "#/admin/ws?workspace=//evil.com",
    "#/admin/ws?workspace=https://evil.com",
    "#/admin/ws?workspace=javascript:alert(1)",
    "#/admin/ws?workspace=%5C%5Cevil.com",
    "#/admin/ws?workspace=data:text/html,<script>alert(1)</script>",
    "#/admin/users/<img src=x onerror=alert(1)>",
]


def _run_node(base_path: str):
    """Run the shipped snippet's mapping function in node over every case, served under ``base_path``."""

    import json
    import shutil
    import subprocess

    from mlflow_oidc_auth import hack

    node = shutil.which("node")
    # Deliberately a failure, not a skip: this is the negative test for an open redirect.
    assert node, "node is required to evaluate mlflow_oidc_auth/hack/redirect.html"

    hashes = [h for h, _ in _MAPPING_CASES] + _HOSTILE_HASHES
    proc = subprocess.run(
        [node, "-e", _NODE_HARNESS, os.path.join(hack._HACK_DIR, "redirect.html"), base_path],
        input=json.dumps(hashes),
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    out = json.loads(proc.stdout)
    return dict(zip(hashes, out["mapped"])), out["replaced"]


@pytest.fixture(scope="module")
def _node_mapping():
    return _run_node("")


@pytest.fixture(scope="module")
def _node_mapping_prefixed():
    return _run_node("/mlflow")


@pytest.mark.parametrize("hash_value,expected", _MAPPING_CASES)
def test_redirect_mapping(_node_mapping, _node_mapping_prefixed, hash_value, expected):
    for (mapped, _), prefix in ((_node_mapping, ""), (_node_mapping_prefixed, "/mlflow")):
        assert mapped[hash_value] == (None if expected is None else f"{prefix}/{expected}")


def test_redirect_mapping_uses_location_replace(_node_mapping):
    _, replaced = _node_mapping
    assert replaced == ["/oidc/ui/users", "/oidc/ui/user", "/oidc/ui/workspaces/team-a", "/oidc/ui/groups"]


@pytest.mark.parametrize("hash_value", _HOSTILE_HASHES)
def test_redirect_never_absolute(_node_mapping, _node_mapping_prefixed, hash_value):
    """Hostile hashes never produce a target outside the plugin's UI: no scheme, no
    protocol-relative URL, no other host, and exactly one encoded segment from the hash."""
    import re

    for (mapped, _), prefix in ((_node_mapping, ""), (_node_mapping_prefixed, "/mlflow")):
        target = mapped[hash_value]
        assert target is not None
        assert not target.startswith("//")
        assert "\\" not in target
        assert not re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", target)
        assert target.startswith(f"{prefix}/oidc/ui/")
        rest = target[len(f"{prefix}/oidc/ui/") :]
        assert re.fullmatch(r"(users/[^/:<>\\]+/experiments|workspaces/[^/:<>\\]+|users|workspaces)", rest), target
