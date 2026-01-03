
import pytest
from unittest.mock import patch, MagicMock
from code_scanner.cli import run_service

def test_service_daemonization():
    """Test that run_service performs double-fork and starts uvicorn."""
    with patch("os.fork") as mock_fork, \
         patch("os.setsid") as mock_setsid, \
         patch("code_scanner.cli.check_server_lock") as mock_lock, \
         patch("uvicorn.Server.run") as mock_run, \
         patch("pathlib.Path.mkdir"), \
         patch("pathlib.Path.write_text"), \
         patch("builtins.open"):
        
        # Simulate child process path:
        # 1. First fork returns 0 (we are child)
        # 2. Second fork returns 0 (we are grandchild/daemon)
        mock_fork.side_effect = [0, 0]
        
        args = MagicMock()
        run_service(args)
        
        # Assertion checks
        assert mock_fork.call_count == 2
        mock_setsid.assert_called_once()
        mock_run.assert_called_once()

def test_service_parent_exit():
    """Test that parent process exits after first fork."""
    with patch("os.fork") as mock_fork, \
         patch("code_scanner.cli.check_server_lock") as mock_lock, \
         patch("sys.exit") as mock_exit:
        
        # Simulate parent process: fork returns PID > 0
        mock_fork.return_value = 12345
        mock_exit.side_effect = SystemExit(0)
        
        args = MagicMock()
        
        with pytest.raises(SystemExit):
            run_service(args)
        
        # Parent should exit with 0
        mock_exit.assert_called_with(0)
