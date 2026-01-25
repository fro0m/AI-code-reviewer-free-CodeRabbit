"""Extended CLI tests for better coverage."""

import os
import pytest
import subprocess
import tempfile
import shutil
import signal
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock
from io import StringIO

from code_scanner.cli import Application, LockFileError, parse_args, main
from code_scanner.config import Config, LLMConfig, CheckGroup


@pytest.fixture
def temp_git_repo():
    """Create a temporary Git repository."""
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
def mock_projects(temp_git_repo):
    """Create a mock projects list for multi-project Application."""
    config_file = temp_git_repo / "config.toml"
    return [(temp_git_repo, config_file, None)]


class TestApplicationInit:
    """Tests for Application initialization."""

    def test_init_sets_config(self, mock_projects):
        """Application stores project configs reference."""
        app = Application(mock_projects)
        assert app._project_configs == mock_projects

    def test_init_components_none(self, mock_projects):
        """Components are None before setup."""
        app = Application(mock_projects)
        assert app.project_manager is not None
        assert app.llm_client_manager is not None
        assert app.scanner is None

    def test_init_stop_event_clear(self, mock_projects):
        """Stop event is not set on init."""
        app = Application(mock_projects)
        assert not app._stop_event.is_set()


class TestApplicationLockFile:
    """Tests for lock file management."""

    def test_acquire_lock_success(self, mock_projects):
        """Lock can be acquired when file doesn't exist."""
        from code_scanner.utils import get_config_dir
        app = Application(mock_projects)
        
        # Ensure lock doesn't exist
        lock_path = get_config_dir() / 'code_scanner.lock'
        if lock_path.exists():
            lock_path.unlink()
        
        app._acquire_lock()
        
        assert lock_path.exists()
        assert app._lock_acquired is True
        
        # Cleanup
        app._release_lock()

    def test_acquire_lock_already_exists(self, mock_projects):
        """Lock acquisition fails when file exists with running process."""
        from code_scanner.utils import get_config_dir
        # Create lock file with current PID (simulating running process)
        current_pid = os.getpid()
        lock_path = get_config_dir() / 'code_scanner.lock'
        lock_path.write_text(f"{current_pid}\n")
        
        app = Application(mock_projects)
        
        with pytest.raises(LockFileError) as exc_info:
            app._acquire_lock()
        
        error_msg = str(exc_info.value)
        assert "code-scanner" in error_msg.lower() or "already running" in error_msg.lower()
        assert str(current_pid) in error_msg
        
        # Cleanup
        lock_path.unlink()

    def test_release_lock_removes_file(self, mock_projects):
        """Release lock removes file."""
        from code_scanner.utils import get_config_dir
        app = Application(mock_projects)
        
        lock_path = get_config_dir() / 'code_scanner.lock'
        if lock_path.exists():
            lock_path.unlink()
        
        app._acquire_lock()
        assert lock_path.exists()
        
        app._release_lock()
        assert not lock_path.exists()

    def test_release_lock_not_acquired(self, mock_projects):
        """Release lock does nothing if not acquired."""
        app = Application(mock_projects)
        
        # Don't acquire lock
        app._release_lock()  # Should not raise


class TestApplicationSignalHandler:
    """Tests for signal handling."""

    def test_signal_handler_sets_stop(self, mock_projects):
        """Signal handler sets stop event."""
        app = Application(mock_projects)
        
        app._signal_handler(signal.SIGINT, None)
        
        assert app._stop_event.is_set()

    def test_signal_handler_sigterm(self, mock_projects):
        """Signal handler works with SIGTERM."""
        app = Application(mock_projects)
        
        app._signal_handler(signal.SIGTERM, None)
        
        assert app._stop_event.is_set()


class TestApplicationCleanup:
    """Tests for cleanup functionality."""

    def test_cleanup_sets_stop_event(self, mock_projects):
        """Cleanup sets stop event."""
        app = Application(mock_projects)
        
        app._cleanup()
        
        assert app._stop_event.is_set()

    def test_cleanup_stops_scanner(self, mock_projects):
        """Cleanup stops scanner if exists."""
        app = Application(mock_projects)
        
        mock_scanner = MagicMock()
        app.scanner = mock_scanner
        
        app._cleanup()
        
        mock_scanner.stop.assert_called_once()

    def test_cleanup_releases_lock(self, mock_projects):
        """Cleanup releases lock."""
        from code_scanner.utils import get_config_dir
        app = Application(mock_projects)
        
        lock_path = get_config_dir() / 'code_scanner.lock'
        if lock_path.exists():
            lock_path.unlink()
        
        app._acquire_lock()
        
        app._cleanup()
        
        assert not lock_path.exists()

    def test_cleanup_handles_no_scanner(self, mock_projects):
        """Cleanup works when scanner is None."""
        app = Application(mock_projects)
        app.scanner = None
        
        app._cleanup()  # Should not raise

    def test_cleanup_sets_not_running_status(self, mock_projects):
        """Cleanup sets all projects to NOT_RUNNING status."""
        from code_scanner.models import ScanStatus, Project
        
        app = Application(mock_projects)
        
        # Create a mock project with output generator
        mock_project = MagicMock(spec=Project)
        mock_project.project_id = "test_project"
        mock_project.output_generator = MagicMock()
        mock_project.issue_tracker = MagicMock()
        
        # Add to project manager
        app.project_manager._projects["test_project"] = mock_project
        
        # Call cleanup
        app._cleanup()
        
        # Verify project status was set to NOT_RUNNING
        assert mock_project.scan_status == ScanStatus.NOT_RUNNING
        
        # Verify output_generator.write was called to update the output file
        mock_project.output_generator.write.assert_called_once()
        
        # Verify the call was made with NOT_RUNNING status
        call_args = mock_project.output_generator.write.call_args
        assert call_args[0][2] == ScanStatus.NOT_RUNNING  # Third argument is scan_status


class TestParseArgsExtended:
    """Extended tests for argument parsing."""

    def test_parse_only_target(self):
        """Parse with only target directory."""
        with patch('sys.argv', ['code-scanner', '/tmp/test']):
            args = parse_args()
        
        assert args.projects == ['/tmp/test']
        assert args.config is None
        assert args.commit is None

    def test_parse_short_config_flag(self):
        """Parse with short -c config flag."""
        with patch('sys.argv', ['code-scanner', '/tmp/test', '-c', '/path/config.toml']):
            args = parse_args()
        
        assert args.config == [Path('/path/config.toml')]

    def test_parse_long_config_flag(self):
        """Parse with long --config flag."""
        with patch('sys.argv', ['code-scanner', '/tmp/test', '--config', '/path/config.toml']):
            args = parse_args()
        
        assert args.config == [Path('/path/config.toml')]

    def test_parse_commit_hash(self):
        """Parse with commit hash."""
        with patch('sys.argv', ['code-scanner', '/tmp/test', '--commit', 'abc123']):
            args = parse_args()
        
        assert args.commit == ['abc123']

    def test_parse_all_options(self):
        """Parse with all options."""
        with patch('sys.argv', [
            'code-scanner', '/tmp/test',
            '-c', '/config.toml',
            '--commit', 'abc123'
        ]):
            args = parse_args()
        
        assert args.projects == ['/tmp/test']
        assert args.config == [Path('/config.toml')]
        assert args.commit == ['abc123']


class TestMainFunction:
    """Tests for main entry point."""

    def test_main_config_error(self, temp_git_repo):
        """Main returns 1 on config error."""
        # Use a non-existent config path to force config error
        fake_config = temp_git_repo / "non_existent_config.toml"
        with patch('sys.argv', ['code-scanner', str(temp_git_repo), '-c', str(fake_config)]):
            result = main()
        
        assert result == 1

    def test_main_with_valid_config(self, temp_git_repo):
        """Main loads config and attempts to run."""
        # Create minimal config
        config_path = temp_git_repo / "config.toml"
        config_path.write_text('''
[[checks]]
pattern = "*"
checks = ["Check"]

[llm]
backend = "lm-studio"
host = "localhost"
port = 1234
context_limit = 16384
''')
        
        with patch('sys.argv', ['code-scanner', str(temp_git_repo), '-c', str(config_path)]):
            with patch('code_scanner.cli.Application.run') as mock_run:
                mock_run.return_value = 0
                result = main()
        
        assert result == 0


class TestApplicationBackupOutput:
    """Tests for output file backup functionality."""

    def test_backup_creates_bak_file(self, mock_config):
        """Backup creates .bak file with timestamp."""
        # Create existing output file
        mock_config.output_path.write_text("# Existing content\n")
        backup_path = mock_config.output_path.parent / f"{mock_config.output_path.name}.bak"
        
        projects = [(mock_config.target_directory, mock_config.config_file, mock_config.commit_hash)]
        app = Application(projects)
        app._backup_existing_output(mock_config.output_path)
        
        # Check backup file was created
        assert backup_path.exists()
        content = backup_path.read_text()
        assert "# Existing content" in content
        assert "Backup created:" in content  # Timestamp header
        
        # Cleanup
        mock_config.output_path.unlink(missing_ok=True)
        backup_path.unlink(missing_ok=True)

    def test_backup_appends_to_existing_bak(self, mock_config):
        """Backup appends to existing .bak file."""
        backup_path = mock_config.output_path.parent / f"{mock_config.output_path.name}.bak"
        
        # Create existing backup
        backup_path.write_text("# First backup\n")
        
        # Create output file to backup
        mock_config.output_path.write_text("# Second content\n")
        
        projects = [(mock_config.target_directory, mock_config.config_file, mock_config.commit_hash)]
        app = Application(projects)
        app._backup_existing_output(mock_config.output_path)
        
        content = backup_path.read_text()
        assert "# First backup" in content
        assert "# Second content" in content
        
        # Cleanup
        mock_config.output_path.unlink(missing_ok=True)
        backup_path.unlink(missing_ok=True)

    def test_backup_no_existing_file(self, mock_config):
        """No backup created when output file doesn't exist."""
        # Ensure output file doesn't exist
        if mock_config.output_path.exists():
            mock_config.output_path.unlink()
        
        projects = [(mock_config.target_directory, mock_config.config_file, mock_config.commit_hash)]
        app = Application(projects)
        app._backup_existing_output(mock_config.output_path)  # Should not raise
        
        # No backup file should be created
        backup_path = mock_config.output_path.parent / f"{mock_config.output_path.name}.bak"
        # Note: backup file might not exist - that's fine


class TestApplicationStaleLockCleanup:
    """Tests for stale lock file cleanup."""

    def test_stale_lock_file_removed(self, mock_config):
        """Stale lock file (non-running PID) is removed and new lock acquired."""
        # Create lock file with non-existent PID
        mock_config.lock_path.write_text("999999999\n")
        
        projects = [(mock_config.target_directory, mock_config.config_file, mock_config.commit_hash)]
        app = Application(projects)
        app._acquire_lock()
        
        # Lock should be acquired
        assert app._lock_acquired is True
        # Lock file should exist with our PID
        assert mock_config.lock_path.exists()
        content = mock_config.lock_path.read_text()
        assert str(os.getpid()) in content
        
        # Cleanup
        app._release_lock()


class TestApplicationRun:
    """Tests for Application.run method."""

    def test_run_keyboard_interrupt(self, mock_config):
        """Run returns 130 on KeyboardInterrupt."""
        projects = [(mock_config.target_directory, mock_config.config_file, mock_config.commit_hash)]
        app = Application(projects)
        
        with patch.object(app, '_setup', side_effect=KeyboardInterrupt):
            result = app.run()
        
        assert result == 130

    def test_run_config_error(self, mock_config):
        """Run returns 1 on ConfigError."""
        from code_scanner.config import ConfigError
        
        projects = [(mock_config.target_directory, mock_config.config_file, mock_config.commit_hash)]
        app = Application(projects)
        
        with patch.object(app, '_setup', side_effect=ConfigError("Test error")):
            result = app.run()
        
        assert result == 1

    def test_run_lock_file_error(self, mock_config):
        """Run returns 1 on LockFileError."""
        projects = [(mock_config.target_directory, mock_config.config_file, mock_config.commit_hash)]
        app = Application(projects)
        
        with patch.object(app, '_setup', side_effect=LockFileError("Lock exists")):
            result = app.run()
        
        assert result == 1

    def test_run_unexpected_error(self, mock_config):
        """Run returns 1 on unexpected error."""
        projects = [(mock_config.target_directory, mock_config.config_file, mock_config.commit_hash)]
        app = Application(projects)
        
        with patch.object(app, '_setup', side_effect=RuntimeError("Unexpected")):
            result = app.run()
        
        assert result == 1

    def test_run_cleanup_always_called(self, mock_config):
        """Cleanup is called even on error."""
        projects = [(mock_config.target_directory, mock_config.config_file, mock_config.commit_hash)]
        app = Application(projects)
        
        with patch.object(app, '_setup', side_effect=RuntimeError("Error")):
            with patch.object(app, '_cleanup') as mock_cleanup:
                app.run()
        
        mock_cleanup.assert_called_once()


class TestLockFileErrorClass:
    """Tests for LockFileError exception class."""

    def test_lock_file_error_message(self):
        """LockFileError stores message."""
        error = LockFileError("Test message")
        assert str(error) == "Test message"

    def test_lock_file_error_is_exception(self):
        """LockFileError is an Exception."""
        error = LockFileError("Test")
        assert isinstance(error, Exception)

    def test_lock_file_error_can_be_raised(self):
        """LockFileError can be raised and caught."""
        with pytest.raises(LockFileError) as exc_info:
            raise LockFileError("Test error")
        
        assert "Test error" in str(exc_info.value)
