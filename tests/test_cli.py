"""Tests for CLI and Application functionality."""

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from code_scanner.cli import (
    Application,
    LockFileError,
    parse_args,
)
from code_scanner.config import Config
from code_scanner.models import LLMConfig, CheckGroup


class TestParseArgs:
    """Tests for parse_args function."""

    def test_parse_target_directory_only(self):
        """Parse with only target directory."""
        with patch.object(sys, 'argv', ['code-scanner', '/path/to/project']):
            args = parse_args()
            assert args.projects == ['/path/to/project']
            assert args.config is None
            assert args.commit is None

    def test_parse_with_config(self):
        """Parse with config file."""
        with patch.object(sys, 'argv', ['code-scanner', '/project', '-c', '/config.toml']):
            args = parse_args()
            assert args.config == [Path('/config.toml')]

    def test_parse_with_commit(self):
        """Parse with commit hash."""
        with patch.object(sys, 'argv', ['code-scanner', '/project', '--commit', 'abc123']):
            args = parse_args()
            assert args.commit == ['abc123']

    def test_parse_all_options(self):
        """Parse with all options."""
        with patch.object(sys, 'argv', [
            'code-scanner', '/project',
            '-c', '/config.toml',
            '--commit', 'abc123'
        ]):
            args = parse_args()
            assert args.projects == ['/project']
            assert args.config == [Path('/config.toml')]
            assert args.commit == ['abc123']





class TestApplicationLockFile:
    """Tests for Application lock file handling."""

    @pytest.fixture(autouse=True)
    def mock_config_dir(self, tmp_path):
        """Mock get_config_dir to use tmp_path."""
        with patch('code_scanner.utils.get_config_dir', return_value=tmp_path):
            yield

    def test_acquire_lock_creates_file(self, tmp_path):
        """Acquire lock creates lock file."""
        # Create a single project tuple
        projects = [(tmp_path, tmp_path / "config.toml", None)]
        
        app = Application(projects)
        app._acquire_lock()
        
        # Lock file should be in config directory
        from code_scanner.utils import get_config_dir
        lock_path = get_config_dir() / 'code_scanner.lock'
        assert lock_path.exists()
        assert app._lock_acquired is True
        
        # Cleanup
        app._release_lock()

    def test_acquire_lock_fails_if_process_running(self, tmp_path):
        """Acquire lock fails if lock file exists and process is running."""
        # Create a single project tuple
        projects = [(tmp_path, tmp_path / "config.toml", None)]
        
        # Create existing lock with current process PID (definitely running)
        from code_scanner.utils import get_config_dir
        lock_path = get_config_dir() / 'code_scanner.lock'
        import os
        lock_path.write_text(str(os.getpid()))
        
        app = Application(projects)
        
        with pytest.raises(LockFileError, match="Another code-scanner instance is already running"):
            app._acquire_lock()
        
        # Cleanup
        if lock_path.exists():
            lock_path.unlink()

    def test_acquire_lock_removes_stale_lock(self, tmp_path):
        """Acquire lock removes stale lock if process is not running."""
        # Create a single project tuple
        projects = [(tmp_path, tmp_path / "config.toml", None)]
        
        # Create existing lock with a PID that's definitely not running
        from code_scanner.utils import get_config_dir
        lock_path = get_config_dir() / 'code_scanner.lock'
        lock_path.write_text("999999999")
        
        app = Application(projects)
        app._acquire_lock()
        
        # Lock should be acquired with our PID
        assert app._lock_acquired is True
        import os
        assert lock_path.read_text().strip() == str(os.getpid())
        
        # Cleanup
        app._release_lock()

    def test_release_lock_removes_file(self, tmp_path):
        """Release lock removes lock file."""
        # Create a single project tuple
        projects = [(tmp_path, tmp_path / "config.toml", None)]
        
        from code_scanner.utils import get_config_dir
        lock_path = get_config_dir() / 'code_scanner.lock'
        
        # Create lock file
        lock_path.write_text("1234")
        
        app = Application(projects)
        app._lock_acquired = True
        app._release_lock()
        
        assert not lock_path.exists()
        assert app._lock_acquired is False

    def test_release_lock_does_nothing_if_not_acquired(self, tmp_path):
        """Release lock does nothing if lock not acquired."""
        # Create a single project tuple
        projects = [(tmp_path, tmp_path / "config.toml", None)]
        
        from code_scanner.utils import get_config_dir
        lock_path = get_config_dir() / 'code_scanner.lock'
        
        # Create file but don't mark as acquired
        lock_path.write_text("1234")
        
        app = Application(projects)
        app._lock_acquired = False
        
        app._release_lock()
        
        # File should still exist
        assert lock_path.exists()

    def test_acquire_lock_registers_atexit_handler(self, tmp_path):
        """Acquire lock registers atexit handler for cleanup on any exit."""
        # Create a single project tuple
        projects = [(tmp_path, tmp_path / "config.toml", None)]
        
        app = Application(projects)
        
        with patch('code_scanner.cli.atexit.register') as mock_atexit:
            app._acquire_lock()
            
            # Verify atexit.register was called with _release_lock
            mock_atexit.assert_called_once_with(app._release_lock)
        
        # Cleanup
        app._release_lock()

    def test_lock_released_via_atexit_on_keyboard_interrupt(self, tmp_path):
        """Lock is released via atexit when KeyboardInterrupt occurs."""
        # Create a single project tuple
        projects = [(tmp_path, tmp_path / "config.toml", None)]
        
        from code_scanner.utils import get_config_dir
        lock_path = get_config_dir() / 'code_scanner.lock'
        
        # Create lock file
        lock_path.write_text("12345")
        
        app = Application(projects)
        
        # Simulate lock acquisition
        app._acquire_lock()
        assert lock_path.exists()
        
        # Simulate calling the registered atexit handler (as would happen on exit)
        app._release_lock()
        
        assert not lock_path.exists()
        assert app._lock_acquired is False

class TestApplicationSignalHandler:
    """Tests for Application signal handling."""

    def test_signal_handler_sets_stop_event(self, tmp_path):
        """Signal handler sets stop event."""
        # Create a single project tuple
        projects = [(tmp_path, tmp_path / "config.toml", None)]
        
        app = Application(projects)
        
        assert not app._stop_event.is_set()
        
        app._signal_handler(2, None)  # SIGINT
        
        assert app._stop_event.is_set()


class TestApplicationCleanup:
    """Tests for Application cleanup."""

    def test_cleanup_stops_scanner(self, tmp_path):
        """Cleanup stops scanner."""
        # Create a single project tuple
        projects = [(tmp_path, tmp_path / "config.toml", None)]
        
        app = Application(projects)
        app.scanner = MagicMock()
        app._lock_acquired = False
        
        app._cleanup()
        
        app.scanner.stop.assert_called_once()

    def test_cleanup_releases_lock(self, tmp_path):
        """Cleanup releases lock."""
        # Create a single project tuple
        projects = [(tmp_path, tmp_path / "config.toml", None)]
        
        from code_scanner.utils import get_config_dir
        lock_path = get_config_dir() / 'code_scanner.lock'
        lock_path.write_text("1234")
        
        app = Application(projects)
        app._lock_acquired = True
        
        app._cleanup()
        
        assert not lock_path.exists()

    def test_cleanup_handles_no_scanner(self, tmp_path):
        """Cleanup handles case when scanner is None."""
        # Create a single project tuple
        projects = [(tmp_path, tmp_path / "config.toml", None)]
        
        app = Application(projects)
        app.scanner = None
        app._lock_acquired = False
        
        # Should not raise
        app._cleanup()


class TestLockFileError:
    """Tests for LockFileError exception."""

    def test_lock_file_error_message(self):
        """LockFileError has proper message."""
        error = LockFileError("Lock file exists")
        assert str(error) == "Lock file exists"

    def test_lock_file_error_is_exception(self):
        """LockFileError is an Exception."""
        assert issubclass(LockFileError, Exception)
