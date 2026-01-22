"""Cross-platform path handling tests."""

import os
import platform
import pytest
from pathlib import Path
from unittest.mock import patch

from code_scanner.utils import get_config_dir


class TestGetConfigDir:
    """Test get_config_dir function for cross-platform compatibility."""

    def test_linux_config_dir(self):
        """Test Linux config directory path."""
        with patch('platform.system', return_value='Linux'):
            config_dir = get_config_dir()
            assert config_dir == Path.home() / ".code-scanner"

    def test_darwin_config_dir(self):
        """Test macOS config directory path."""
        with patch('platform.system', return_value='Darwin'):
            config_dir = get_config_dir()
            assert config_dir == Path.home() / "Library" / "Application Support" / "code-scanner"

    def test_windows_config_dir_with_appdata(self):
        """Test Windows config directory path with APPDATA set."""
        with patch('platform.system', return_value='Windows'):
            with patch.dict(os.environ, {'APPDATA': 'C:\\Users\\test\\AppData\\Roaming'}):
                config_dir = get_config_dir()
                # Check that path contains the expected components
                assert 'code-scanner' in str(config_dir)
                assert 'test' in str(config_dir)
                assert 'AppData' in str(config_dir)

    def test_windows_config_dir_fallback(self):
        """Test Windows config directory path fallback when APPDATA not set."""
        with patch('platform.system', return_value='Windows'):
            with patch.dict(os.environ, {}, clear=True):
                config_dir = get_config_dir()
                # Should fallback to home directory
                assert config_dir == Path.home() / ".code-scanner"

    def test_config_dir_returns_correct_path(self):
        """Test that get_config_dir returns correct path for current platform."""
        config_dir = get_config_dir()
        # Just verify it returns a path
        assert isinstance(config_dir, Path)
        # Verify it contains 'code-scanner'
        assert 'code-scanner' in str(config_dir)

    def test_config_dir_existing_directory(self, tmp_path):
        """Test that config directory is not recreated if it exists."""
        config_dir = tmp_path / ".code-scanner"
        config_dir.mkdir()
        
        # Store original mtime
        original_mtime = config_dir.stat().st_mtime
        
        with patch('platform.system', return_value='Linux'):
            with patch('code_scanner.utils.Path.home', return_value=tmp_path):
                # Don't mock mkdir, let it handle exist_ok=True
                get_config_dir()
        
        # Directory should still exist with same mtime (not recreated)
        assert config_dir.exists()
        assert config_dir.stat().st_mtime == original_mtime
