
import pytest
from unittest.mock import patch, MagicMock
from code_scanner.cli import main
import argparse

@pytest.fixture
def mock_httpx_post():
    with patch("httpx.post") as mock:
        yield mock

@pytest.fixture
def mock_httpx_get():
    with patch("httpx.get") as mock:
        yield mock

def test_cli_add(mock_httpx_post):
    with patch("sys.argv", ["code-scanner", "add", "/tmp/test"]):
        mock_httpx_post.return_value.status_code = 200
        main()
        mock_httpx_post.assert_called_once()
        assert mock_httpx_post.call_args[0][0].endswith("/watch/add")
        assert mock_httpx_post.call_args[1]["json"]["path"] == "/tmp/test"

def test_cli_remove(mock_httpx_post):
    with patch("sys.argv", ["code-scanner", "remove", "/tmp/test"]):
        mock_httpx_post.return_value.status_code = 200
        main()
        mock_httpx_post.assert_called_once()
        assert mock_httpx_post.call_args[0][0].endswith("/watch/remove")

def test_cli_list(mock_httpx_get):
    with patch("sys.argv", ["code-scanner", "list"]):
        mock_httpx_get.return_value.status_code = 200
        mock_httpx_get.return_value.json.return_value = [
            {"target_directory": "/tmp/test", "is_running": True, "total_issues": 5}
        ]
        with patch("builtins.print") as mock_print:
            main()
            # Basic verify output contains expected string
            calls = [str(call) for call in mock_print.mock_calls]
            assert any("/tmp/test" in call for call in calls)
