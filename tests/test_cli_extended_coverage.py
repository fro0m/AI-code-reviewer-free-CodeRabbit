"""Extended coverage tests for CLI module - targeting uncovered paths."""

import os
import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from code_scanner.cli import Application, LockFileError
from code_scanner.config import Config, ConfigError, LLMConfig, CheckGroup
from code_scanner.llm_client_manager import LLMClientManager


@pytest.fixture
def temp_git_repo():
    """Create a temporary Git repository."""
    import shutil
    import subprocess
    temp_dir = tempfile.mkdtemp()
    
    subprocess.run(['git', 'init', '-q'], cwd=temp_dir, check=True)
    subprocess.run(['git', 'config', 'user.email', 'test@test.com'], cwd=temp_dir, check=True)
    subprocess.run(['git', 'config', 'user.name', 'Test'], cwd=temp_dir, check=True)
    
    readme = Path(temp_dir) / "README.md"
    readme.write_text("# Test\n")
    subprocess.run(['git', 'add', '.'], cwd=temp_dir, check=True)
    subprocess.run(['git', 'commit', '-m', 'Initial', '-q'], cwd=temp_dir, check=True)
    
    yield Path(temp_dir)
    
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def mock_config(temp_git_repo):
    """Create a mock Config object."""
    config = MagicMock(spec=Config)
    config.target_directory = temp_git_repo
    config.output_path = temp_git_repo / "results.md"
    config.log_path = temp_git_repo / "scanner.log"
    config.lock_path = temp_git_repo / ".code_scanner.lock"
    config.config_file = temp_git_repo / "config.toml"
    config.output_file = "results.md"
    config.log_file = "scanner.log"
    config.git_poll_interval = 0.1
    config.llm_retry_interval = 0.1
    config.max_llm_retries = 2
    config.check_groups = [CheckGroup(pattern="*", checks=["Check"])]
    config.llm = LLMConfig(backend="lm-studio", host="localhost", port=1234, context_limit=16384)
    config.commit_hash = None
    return config


class TestLLMClientManagerCoverage:
    """Test LLMClientManager edge cases."""

    def test_invalid_backend_raises_value_error(self):
        """Test invalid backend configuration raises ValueError."""
        # LLMConfig validates backend in __post_init__, so we expect ValueError from constructor
        with pytest.raises(ValueError) as exc_info:
            invalid_config = LLMConfig(
                backend="invalid-backend",
                host="localhost",
                port=1234,
                model="test",
                context_limit=16384
            )
        
        error_msg = str(exc_info.value)
        assert "Invalid backend" in error_msg
        assert "invalid-backend" in error_msg

    def test_lm_studio_backend(self):
        """Test LM Studio backend client creation."""
        manager = LLMClientManager()
        config = LLMConfig(
            backend="lm-studio",
            host="localhost",
            port=1234,
            model="test",
            context_limit=16384
        )
        
        with patch('code_scanner.lmstudio_client.LMStudioClient') as MockClient:
            MockClient.return_value = MagicMock()
            client = manager._create_client_from_config(config)
            MockClient.assert_called_once()

    def test_ollama_backend(self):
        """Test Ollama backend client creation."""
        manager = LLMClientManager()
        config = LLMConfig(
            backend="ollama",
            host="localhost",
            port=11434,
            model="qwen3:4b",
            context_limit=16384
        )
        
        with patch('code_scanner.ollama_client.OllamaClient') as MockClient:
            MockClient.return_value = MagicMock()
            client = manager._create_client_from_config(config)
            MockClient.assert_called_once()


class TestLockFileCoverage:
    """Test lock file handling edge cases."""

    def test_invalid_lock_file_contents(self, temp_git_repo):
        """Test handling of corrupt lock file with non-numeric content."""
        from code_scanner.utils import get_config_dir
        
        # Write invalid content to lock file
        lock_path = get_config_dir() / 'code_scanner.lock'
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.write_text("not-a-pid")
        
        # Create app with a single project
        app = Application([(temp_git_repo, temp_git_repo / "config.toml", None)])
        
        # Should remove invalid lock and acquire new one
        app._acquire_lock()
        
        assert app._lock_acquired
        # Lock file should now contain valid PID
        assert lock_path.read_text().strip().isdigit()
        
        app._release_lock()
        # Clean up
        if lock_path.exists():
            lock_path.unlink()

    def test_stale_lock_from_dead_process(self, temp_git_repo):
        """Test removal of stale lock from terminated process."""
        from code_scanner.utils import get_config_dir
        
        # Write a PID that almost certainly doesn't exist
        lock_path = get_config_dir() / 'code_scanner.lock'
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.write_text("999999999")
        
        app = Application([(temp_git_repo, temp_git_repo / "config.toml", None)])
        app._acquire_lock()
        
        assert app._lock_acquired
        
        app._release_lock()
        # Clean up
        if lock_path.exists():
            lock_path.unlink()

    def test_active_lock_from_running_process(self, temp_git_repo):
        """Test that active lock from running process raises error."""
        from code_scanner.utils import get_config_dir
        
        # Write current process PID (simulating another instance)
        lock_path = get_config_dir() / 'code_scanner.lock'
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.write_text(f"{os.getpid()}")
        
        app = Application([(temp_git_repo, temp_git_repo / "config.toml", None)])
        
        with pytest.raises(LockFileError) as exc_info:
            app._acquire_lock()
        
        assert "already running" in str(exc_info.value).lower()
        # Clean up
        if lock_path.exists():
            lock_path.unlink()

    def test_lock_file_empty(self, temp_git_repo):
        """Test handling of empty lock file."""
        from code_scanner.utils import get_config_dir
        
        lock_path = get_config_dir() / 'code_scanner.lock'
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.write_text("")
        
        app = Application([(temp_git_repo, temp_git_repo / "config.toml", None)])
        
        # Should handle empty file (ValueError on int conversion)
        app._acquire_lock()
        
        assert app._lock_acquired
        
        app._release_lock()
        # Clean up
        if lock_path.exists():
            lock_path.unlink()


class TestBackupExistingOutputCoverage:
    """Test _backup_existing_output edge cases."""

    def test_backup_io_error(self, temp_git_repo, monkeypatch):
        """Test handling of backup failure."""
        # Create existing output file
        output_path = temp_git_repo / "results.md"
        output_path.write_text("existing content")
        
        app = Application([(temp_git_repo, temp_git_repo / "config.toml", None)])
        
        # Make backup path unwritable
        backup_path = output_path.parent / f"{output_path.name}.bak"
        
        original_open = open
        def failing_open(path, mode='r', **kwargs):
            if str(path) == str(backup_path) and 'a' in mode:
                raise IOError("Disk full")
            return original_open(path, mode, **kwargs)
        
        # Should handle the error gracefully
        with patch('builtins.open', failing_open):
            app._backup_existing_output(output_path)  # Should not raise

    def test_backup_no_existing_output(self, temp_git_repo):
        """Test backup when no existing output file."""
        output_path = temp_git_repo / "results.md"
        app = Application([(temp_git_repo, temp_git_repo / "config.toml", None)])
        
        # Ensure output doesn't exist
        if output_path.exists():
            output_path.unlink()
        
        # Should not raise
        app._backup_existing_output(output_path)


class TestCleanupCoverage:
    """Test _cleanup method edge cases."""

    def test_cleanup_before_logging_setup(self, temp_git_repo):
        """Test cleanup handles logging not being set up."""
        app = Application([(temp_git_repo, temp_git_repo / "config.toml", None)])
        
        # Simulate state before logging is configured
        app.scanner = None
        app._lock_acquired = False
        
        # Should not raise even if logger might fail
        app._cleanup()

    def test_cleanup_with_scanner(self, temp_git_repo):
        """Test cleanup properly stops scanner."""
        app = Application([(temp_git_repo, temp_git_repo / "config.toml", None)])
        
        mock_scanner = MagicMock()
        app.scanner = mock_scanner
        app._lock_acquired = False
        
        app._cleanup()
        
        mock_scanner.stop.assert_called_once()


class TestIsProcessRunning:
    """Test _is_process_running method."""

    def test_current_process_is_running(self, temp_git_repo):
        """Test that current process is detected as running."""
        app = Application([(temp_git_repo, temp_git_repo / "config.toml", None)])
        
        assert app._is_process_running(os.getpid()) is True

    def test_invalid_pid_not_running(self, temp_git_repo):
        """Test that invalid PID is not running."""
        app = Application([(temp_git_repo, temp_git_repo / "config.toml", None)])
        
        # Very high PID that shouldn't exist
        assert app._is_process_running(999999999) is False


class TestSystemExitHandling:
    """Test Application.run handles SystemExit properly."""

    def test_run_with_system_exit(self, temp_git_repo, monkeypatch):
        """Test Application.run handles SystemExit."""
        app = Application([(temp_git_repo, temp_git_repo / "config.toml", None)])
        
        def setup_that_exits():
            raise SystemExit(1)
        
        monkeypatch.setattr(app, '_setup', setup_that_exits)
        
        with pytest.raises(SystemExit):
            app.run()

    def test_run_with_keyboard_interrupt(self, temp_git_repo, monkeypatch):
        """Test Application.run handles KeyboardInterrupt."""
        app = Application([(temp_git_repo, temp_git_repo / "config.toml", None)])
        
        def setup_that_interrupts():
            raise KeyboardInterrupt()
        
        monkeypatch.setattr(app, '_setup', setup_that_interrupts)
        
        result = app.run()
        
        assert result == 130  # Standard exit code for SIGINT
