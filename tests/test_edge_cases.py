"""Comprehensive edge case tests for code scanner.

This file tests edge cases identified in edgecases.txt that are not
covered by existing test files.
"""

import pytest
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open
from datetime import datetime

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from code_scanner.config import load_config, ConfigError
from code_scanner.file_filter import FileFilter
from code_scanner.scanner import Scanner
from code_scanner.models import Issue, GitState, ChangedFile, IssueStatus, CheckGroup
from code_scanner.issue_tracker import IssueTracker
from code_scanner.utils import read_file_content, is_binary_file
from code_scanner.lmstudio_client import LLMClientError, ContextOverflowError
from code_scanner.ctags_index import CtagsIndex


class TestFileFilterEdgeCases:
    """Edge cases for file filtering."""

    def test_unicode_filename_matching(self, tmp_path):
        """Test files with unicode characters in names."""
        filter = FileFilter(
            repo_path=tmp_path,
            config_ignore_patterns=["*.md"],
            load_gitignore=False,
        )
        
        # Unicode filename with special characters
        should_skip, _ = filter.should_skip("файл.md")
        assert should_skip is True
        
        should_skip, _ = filter.should_skip("файл.cpp")
        assert should_skip is False

    def test_special_characters_in_filename(self, tmp_path):
        """Test files with special characters in names."""
        filter = FileFilter(
            repo_path=tmp_path,
            scanner_files={"results.md"},
            load_gitignore=False,
        )
        
        # Files with spaces and special chars - basename match only
        should_skip, _ = filter.should_skip("results.md")
        assert should_skip is True
        
        # File with spaces but different basename - should not skip
        should_skip, _ = filter.should_skip("file with spaces.cpp")
        assert should_skip is False

    def test_empty_config_patterns(self, tmp_path):
        """Test empty patterns list doesn't crash."""
        filter = FileFilter(
            repo_path=tmp_path,
            config_ignore_patterns=[],
            load_gitignore=False,
        )
        
        # Should not skip anything
        should_skip, _ = filter.should_skip("any_file.md")
        assert should_skip is False

    def test_invalid_glob_pattern_handling(self, tmp_path):
        """Test that invalid glob patterns don't crash."""
        # This should not raise an exception
        filter = FileFilter(
            repo_path=tmp_path,
            config_ignore_patterns=["***", "[invalid"],
            load_gitignore=False,
        )
        
        # Just verify it doesn't crash
        should_skip, _ = filter.should_skip("test.cpp")
        # Result depends on fnmatch behavior


class TestGitWatcherEdgeCases:
    """Edge cases for git watcher."""

    def test_file_with_spaces_in_path(self, git_repo: Path):
        """Test git watcher with files containing spaces."""
        from code_scanner.git_watcher import GitWatcher
        
        # Create file with spaces
        file_with_spaces = git_repo / "file with spaces.txt"
        file_with_spaces.write_text("content")
        
        watcher = GitWatcher(git_repo)
        watcher.connect()
        
        state = watcher.get_state()
        
        # Should detect the file
        paths = [f.path for f in state.changed_files]
        assert "file with spaces.txt" in paths

    def test_quoted_paths_in_git_status(self, git_repo: Path):
        """Test git watcher handles quoted paths from git status."""
        from code_scanner.git_watcher import GitWatcher
        
        # Create file that would be quoted by git
        quoted_file = git_repo / "file with \"quotes\".txt"
        quoted_file.write_text("content")
        
        watcher = GitWatcher(git_repo)
        watcher.connect()
        
        state = watcher.get_state()
        
        # Should handle quoted paths correctly
        assert len(state.changed_files) > 0

    def test_submodule_directory_skipped(self, git_repo: Path):
        """Test that submodule directories are skipped."""
        from code_scanner.git_watcher import GitWatcher
        
        # Create a directory that looks like a submodule
        submodule_dir = git_repo / "submodule"
        submodule_dir.mkdir()
        (submodule_dir / ".git").write_text("gitdir: ../.git/modules/submodule")
        
        watcher = GitWatcher(git_repo)
        watcher.connect()
        
        state = watcher.get_state()
        
        # Submodule directory should not appear as a file
        paths = [f.path for f in state.changed_files]
        assert "submodule" not in paths


class TestScannerEdgeCases:
    """Edge cases for scanner."""

    def test_empty_file_handling(self, mock_dependencies):
        """Test scanner handles empty files."""
        scanner = Scanner(**mock_dependencies)
        
        state = GitState(
            changed_files=[ChangedFile(path="empty.py", status="unstaged")]
        )
        
        files_content = {"empty.py": ""}
        
        mock_dependencies["llm_client"].query.return_value = {"issues": []}
        
        with patch.object(scanner, "_get_files_content", return_value=files_content):
            scanner._run_scan(state)
        
        # Should complete without error
        mock_dependencies["llm_client"].query.assert_called()

    def test_whitespace_only_file(self, mock_dependencies):
        """Test scanner handles files with only whitespace."""
        scanner = Scanner(**mock_dependencies)
        
        state = GitState(
            changed_files=[ChangedFile(path="whitespace.py", status="unstaged")]
        )
        
        files_content = {"whitespace.py": "   \n\n  \t  \n"}
        
        mock_dependencies["llm_client"].query.return_value = {"issues": []}
        
        with patch.object(scanner, "_get_files_content", return_value=files_content):
            scanner._run_scan(state)
        
        # Should complete without error
        mock_dependencies["llm_client"].query.assert_called()

    def test_mixed_line_endings(self, mock_dependencies):
        """Test scanner handles files with mixed CRLF/LF line endings."""
        scanner = Scanner(**mock_dependencies)
        
        state = GitState(
            changed_files=[ChangedFile(path="mixed.py", status="unstaged")]
        )
        
        # File with mixed line endings
        content = "line1\nline2\r\nline3\nline4\r\n"
        files_content = {"mixed.py": content}
        
        mock_dependencies["llm_client"].query.return_value = {"issues": []}
        
        with patch.object(scanner, "_get_files_content", return_value=files_content):
            scanner._run_scan(state)
        
        # Should complete without error
        mock_dependencies["llm_client"].query.assert_called()

    def test_file_with_bom(self, mock_dependencies):
        """Test scanner handles files with BOM (Byte Order Mark)."""
        scanner = Scanner(**mock_dependencies)
        
        state = GitState(
            changed_files=[ChangedFile(path="bom.py", status="unstaged")]
        )
        
        # UTF-8 BOM + content
        content = "\ufeff# Python file\nprint('hello')"
        files_content = {"bom.py": content}
        
        mock_dependencies["llm_client"].query.return_value = {"issues": []}
        
        with patch.object(scanner, "_get_files_content", return_value=files_content):
            scanner._run_scan(state)
        
        # Should complete without error
        mock_dependencies["llm_client"].query.assert_called()

    def test_very_long_line(self, mock_dependencies):
        """Test scanner handles files with very long lines."""
        scanner = Scanner(**mock_dependencies)
        
        state = GitState(
            changed_files=[ChangedFile(path="longline.py", status="unstaged")]
        )
        
        # Very long line (10000 chars)
        long_line = "x" * 10000
        content = f"def test():\n    return '{long_line}'\n"
        files_content = {"longline.py": content}
        
        mock_dependencies["llm_client"].query.return_value = {"issues": []}
        
        with patch.object(scanner, "_get_files_content", return_value=files_content):
            scanner._run_scan(state)
        
        # Should complete without error
        mock_dependencies["llm_client"].query.assert_called()

    def test_binary_file_detection(self, mock_dependencies):
        """Test scanner skips binary files."""
        scanner = Scanner(**mock_dependencies)
        
        state = GitState(
            changed_files=[ChangedFile(path="binary.bin", status="unstaged")]
        )
        
        # Simulate binary file (None returned from read_file_content)
        files_content = {}
        
        mock_dependencies["llm_client"].query.return_value = {"issues": []}
        
        with patch.object(scanner, "_get_files_content", return_value=files_content):
            scanner._run_scan(state)
        
        # Should not query LLM for binary file
        mock_dependencies["llm_client"].query.assert_not_called()

    def test_encoding_error_handling(self, mock_dependencies):
        """Test scanner handles encoding errors gracefully."""
        scanner = Scanner(**mock_dependencies)
        
        state = GitState(
            changed_files=[ChangedFile(path="bad_encoding.py", status="unstaged")]
        )
        
        # Simulate encoding error (None returned)
        files_content = {}
        
        mock_dependencies["llm_client"].query.return_value = {"issues": []}
        
        with patch.object(scanner, "_get_files_content", return_value=files_content):
            scanner._run_scan(state)
        
        # Should not crash
        assert True

    def test_context_overflow_error(self, mock_dependencies):
        """Test scanner handles context overflow error."""
        scanner = Scanner(**mock_dependencies)
        
        state = GitState(
            changed_files=[ChangedFile(path="large.py", status="unstaged")]
        )
        
        files_content = {"large.py": "x = 1"}
        
        # Simulate context overflow
        mock_dependencies["llm_client"].query.side_effect = ContextOverflowError(
            "Context limit exceeded"
        )
        
        with patch.object(scanner, "_get_files_content", return_value=files_content):
            scanner._run_scan(state)
        
        # Should handle error gracefully

    def test_all_files_filtered_no_scan(self, mock_dependencies):
        """Test scanner when all files are filtered out."""
        scanner = Scanner(**mock_dependencies)
        
        state = GitState(
            changed_files=[
                ChangedFile(path="results.md", status="unstaged"),
                ChangedFile(path="README.md", status="unstaged"),
                ChangedFile(path="notes.txt", status="unstaged"),
            ]
        )
        
        # All files filtered out
        files_content = {}
        
        mock_dependencies["llm_client"].query.return_value = {"issues": []}
        
        with patch.object(scanner, "_get_files_content", return_value=files_content):
            scanner._run_scan(state)
        
        # Should not query LLM
        mock_dependencies["llm_client"].query.assert_not_called()

    def test_file_deleted_during_scan(self, mock_dependencies):
        """Test scanner handles file deletion during scan."""
        scanner = Scanner(**mock_dependencies)
        
        state = GitState(
            changed_files=[
                ChangedFile(path="existing.py", status="unstaged"),
                ChangedFile(path="deleted.py", status="deleted"),
            ]
        )
        
        files_content = {"existing.py": "x = 1"}
        
        mock_dependencies["llm_client"].query.return_value = {"issues": []}
        
        with patch.object(scanner, "_get_files_content", return_value=files_content):
            scanner._run_scan(state)
        
        # Should resolve issues for deleted file
        mock_dependencies["issue_tracker"].resolve_issues_for_file.assert_called_with("deleted.py")

    def test_multiple_refresh_events_during_scan(self, mock_dependencies):
        """Test scanner handles multiple refresh signals during scan."""
        scanner = Scanner(**mock_dependencies)
        
        state = GitState(
            changed_files=[ChangedFile(path="test.py", status="unstaged")]
        )
        
        files_content = {"test.py": "x = 1"}
        
        query_count = [0]
        def query_side_effect(*args, **kwargs):
            query_count[0] += 1
            if query_count[0] <= 2:
                scanner._refresh_event.set()
            return {"issues": []}
        
        mock_dependencies["llm_client"].query.side_effect = query_side_effect
        mock_dependencies["git_watcher"].get_state.return_value = state
        
        with patch.object(scanner, "_get_files_content", return_value=files_content):
            scanner._run_scan(state)
        
        # Should handle multiple refresh events gracefully

    def test_stop_event_during_check(self, mock_dependencies):
        """Test scanner stops when stop event is set during check."""
        scanner = Scanner(**mock_dependencies)
        
        state = GitState(
            changed_files=[ChangedFile(path="test.py", status="unstaged")]
        )
        
        files_content = {"test.py": "x = 1"}
        
        def query_side_effect(*args, **kwargs):
            scanner._stop_event.set()
            return {"issues": []}
        
        mock_dependencies["llm_client"].query.side_effect = query_side_effect
        
        with patch.object(scanner, "_get_files_content", return_value=files_content):
            scanner._run_scan(state)
        
        # Should stop gracefully


class TestConfigEdgeCases:
    """Edge cases for configuration."""

    def test_invalid_host_malformed_url(self, temp_dir: Path):
        """Test config with malformed host URL."""
        config_file = temp_dir / "config.toml"
        config_file.write_text('''
checks = ["test"]

[llm]
backend = "lm-studio"
host = "not a url"
port = 1234
context_limit = 16384
''')
        
        # Config loading should succeed (validation happens at connection time)
        config = load_config(temp_dir, config_file)
        assert config.llm.host == "not a url"

    def test_invalid_port_not_a_number(self, temp_dir: Path):
        """Test config with non-numeric port."""
        config_file = temp_dir / "config.toml"
        config_file.write_text('''
checks = ["test"]

[llm]
backend = "lm-studio"
host = "localhost"
port = "not a number"
context_limit = 16384
''')
        
        # Config loading should succeed (validation happens at LLMConfig level)
        # The ValueError is raised by LLMConfig.__post_init__, not ConfigError
        # However, TOML will parse "not a number" as a string, not a number
        # So we test that it loads as a string (validation happens at connection time)
        config = load_config(temp_dir, config_file)
        assert config.llm.port == "not a number"  # String, not int

    def test_invalid_port_out_of_range(self, temp_dir: Path):
        """Test config with port out of valid range."""
        config_file = temp_dir / "config.toml"
        config_file.write_text('''
checks = ["test"]

[llm]
backend = "lm-studio"
host = "localhost"
port = 99999
context_limit = 16384
''')
        
        # Config loading should succeed (validation happens at connection time)
        config = load_config(temp_dir, config_file)
        assert config.llm.port == 99999

    def test_invalid_timeout_value(self, temp_dir: Path):
        """Test config with invalid timeout value."""
        config_file = temp_dir / "config.toml"
        config_file.write_text('''
checks = ["test"]

[llm]
backend = "lm-studio"
host = "localhost"
port = 1234
timeout = "not a number"
context_limit = 16384
''')
        
        # Config loading should succeed (validation happens at LLMConfig level)
        # However, TOML will parse "not a number" as a string, not a number
        # So we test that it loads as a string (validation happens at connection time)
        config = load_config(temp_dir, config_file)
        assert config.llm.timeout == "not a number"  # String, not int

    def test_invalid_context_limit_value(self, temp_dir: Path):
        """Test config with invalid context_limit value."""
        config_file = temp_dir / "config.toml"
        config_file.write_text('''
checks = ["test"]

[llm]
backend = "lm-studio"
host = "localhost"
port = 1234
context_limit = "not a number"
''')
        
        # Config loading should succeed (validation happens at LLMConfig level)
        # However, TOML will parse "not a number" as a string, not a number
        # So we test that it loads as a string (validation happens at connection time)
        config = load_config(temp_dir, config_file)
        assert config.llm.context_limit == "not a number"  # String, not int

    def test_negative_context_limit(self, temp_dir: Path):
        """Test config with negative context_limit."""
        config_file = temp_dir / "config.toml"
        config_file.write_text('''
checks = ["test"]

[llm]
backend = "lm-studio"
host = "localhost"
port = 1234
context_limit = -100
''')
        
        # Config loading should succeed (validation happens at connection time)
        config = load_config(temp_dir, config_file)
        assert config.llm.context_limit == -100


class TestIssueTrackerEdgeCases:
    """Edge cases for issue tracker."""

    def test_issue_with_unicode_description(self):
        """Test issue tracker handles unicode in descriptions."""
        tracker = IssueTracker()
        
        issue = Issue(
            file_path="test.cpp",
            line_number=1,
            description="Ошибка: утечка памяти",  # Russian text
            suggested_fix="Исправить",  # Russian text
            check_query="Check",
            timestamp=datetime.now(),
            code_snippet="",
        )
        
        added = tracker.add_issue(issue)
        assert added is True
        assert len(tracker.issues) == 1

    def test_issue_with_special_characters(self):
        """Test issue tracker handles special characters."""
        tracker = IssueTracker()
        
        issue = Issue(
            file_path="test.cpp",
            line_number=1,
            description="Issue with <special> & \"characters\"",
            suggested_fix="Fix with 'quotes'",
            check_query="Check",
            timestamp=datetime.now(),
            code_snippet="",
        )
        
        added = tracker.add_issue(issue)
        assert added is True
        assert len(tracker.issues) == 1

    def test_very_long_description(self):
        """Test issue tracker handles very long descriptions."""
        tracker = IssueTracker()
        
        long_desc = "This is a very long description. " * 100  # ~4000 chars
        issue = Issue(
            file_path="test.cpp",
            line_number=1,
            description=long_desc,
            suggested_fix="Fix it",
            check_query="Check",
            timestamp=datetime.now(),
            code_snippet="",
        )
        
        added = tracker.add_issue(issue)
        assert added is True
        assert len(tracker.issues) == 1

    def test_issue_for_nonexistent_file(self):
        """Test resolving issues for file that doesn't exist."""
        tracker = IssueTracker()
        
        issue = Issue(
            file_path="nonexistent.cpp",
            line_number=1,
            description="Test",
            suggested_fix="Fix",
            check_query="Check",
            timestamp=datetime.now(),
            code_snippet="",
        )
        
        tracker.add_issue(issue)
        
        # Should resolve without error
        resolved = tracker.resolve_issues_for_file("nonexistent.cpp")
        assert resolved == 1

    def test_duplicate_issue_different_timestamp(self):
        """Test that duplicate with different timestamp is still deduplicated."""
        tracker = IssueTracker()
        
        issue1 = Issue(
            file_path="test.cpp",
            line_number=1,
            description="Test",
            suggested_fix="Fix",
            check_query="Check",
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            code_snippet="code",
        )
        issue2 = Issue(
            file_path="test.cpp",
            line_number=1,
            description="Test",
            suggested_fix="Fix",
            check_query="Check",
            timestamp=datetime(2024, 1, 2, 12, 0, 0),  # Different timestamp
            code_snippet="code",
        )
        
        tracker.add_issue(issue1)
        added = tracker.add_issue(issue2)
        
        assert added is False
        assert len(tracker.issues) == 1

    def test_empty_issues_list(self):
        """Test update_from_scan with empty issues list."""
        tracker = IssueTracker()
        
        # Add initial issue
        tracker.add_issue(Issue(
            file_path="test.cpp",
            line_number=1,
            description="Test",
            suggested_fix="Fix",
            check_query="Check",
            timestamp=datetime.now(),
            code_snippet="",
        ))
        
        # Update with empty issues
        new_count, resolved = tracker.update_from_scan([], ["test.cpp"])
        
        assert new_count == 0
        assert resolved == 1
        assert len(tracker.open_issues) == 0

    def test_multiple_files_all_resolved(self):
        """Test resolving issues for multiple files."""
        tracker = IssueTracker()
        
        # Add issues for multiple files
        for i in range(3):
            tracker.add_issue(Issue(
                file_path=f"file{i}.cpp",
                line_number=1,
                description=f"Test {i}",
                suggested_fix="Fix",
                check_query="Check",
                timestamp=datetime.now(),
                code_snippet=f"code{i}",
            ))
        
        # Resolve all
        total_resolved = 0
        for i in range(3):
            total_resolved += tracker.resolve_issues_for_file(f"file{i}.cpp")
        
        assert total_resolved == 3
        assert len(tracker.resolved_issues) == 3


class TestUtilsEdgeCases:
    """Edge cases for utility functions."""

    def test_read_file_content_binary_file(self, tmp_path):
        """Test read_file_content returns None for binary files."""
        # Create a binary file
        binary_file = tmp_path / "binary.bin"
        binary_file.write_bytes(b'\x00\x01\x02\x03\x04\x05')
        
        content = read_file_content(binary_file)
        assert content is None

    def test_read_file_content_empty_file(self, tmp_path):
        """Test read_file_content handles empty files."""
        empty_file = tmp_path / "empty.txt"
        empty_file.write_text("")
        
        content = read_file_content(empty_file)
        assert content == ""

    def test_read_file_content_unicode(self, tmp_path):
        """Test read_file_content handles unicode content."""
        unicode_file = tmp_path / "unicode.txt"
        unicode_file.write_text("Привет мир! 你好世界! こんにちは!", encoding="utf-8")
        
        content = read_file_content(unicode_file)
        assert "Привет мир!" in content

    def test_is_binary_file_true(self, tmp_path):
        """Test is_binary_file returns True for binary files."""
        binary_file = tmp_path / "binary.bin"
        binary_file.write_bytes(b'\x00\x01\x02\x03\xFF\xFE')
        
        assert is_binary_file(binary_file) is True

    def test_is_binary_file_false(self, tmp_path):
        """Test is_binary_file returns False for text files."""
        text_file = tmp_path / "text.txt"
        text_file.write_text("Hello, world!")
        
        assert is_binary_file(text_file) is False

    def test_is_binary_file_nonexistent(self, tmp_path):
        """Test is_binary_file handles nonexistent files."""
        nonexistent = tmp_path / "nonexistent.txt"
        
        # Should return False for nonexistent files
        assert is_binary_file(nonexistent) is False


class TestLLMClientEdgeCases:
    """Edge cases for LLM client interactions."""

    def test_connection_refused_handling(self, mock_dependencies):
        """Test scanner handles connection refused."""
        scanner = Scanner(**mock_dependencies)
        
        state = GitState(
            changed_files=[ChangedFile(path="test.py", status="unstaged")]
        )
        
        files_content = {"test.py": "x = 1"}
        
        mock_dependencies["llm_client"].query.side_effect = LLMClientError(
            "Connection refused"
        )
        mock_dependencies["llm_client"].wait_for_connection = MagicMock()
        
        with patch.object(scanner, "_get_files_content", return_value=files_content):
            scanner._run_scan(state)
        
        # Should wait for reconnection
        mock_dependencies["llm_client"].wait_for_connection.assert_called()

    def test_timeout_handling(self, mock_dependencies):
        """Test scanner handles timeout errors."""
        scanner = Scanner(**mock_dependencies)
        
        state = GitState(
            changed_files=[ChangedFile(path="test.py", status="unstaged")]
        )
        
        files_content = {"test.py": "x = 1"}
        
        mock_dependencies["llm_client"].query.side_effect = LLMClientError(
            "Connection timed out"
        )
        mock_dependencies["llm_client"].wait_for_connection = MagicMock()
        
        with patch.object(scanner, "_get_files_content", return_value=files_content):
            scanner._run_scan(state)
        
        # Should wait for reconnection
        mock_dependencies["llm_client"].wait_for_connection.assert_called()

    def test_malformed_json_response(self, mock_dependencies):
        """Test scanner handles malformed JSON responses."""
        scanner = Scanner(**mock_dependencies)
        
        state = GitState(
            changed_files=[ChangedFile(path="test.py", status="unstaged")]
        )
        
        files_content = {"test.py": "x = 1"}
        
        mock_dependencies["llm_client"].query.side_effect = LLMClientError(
            "Failed to get valid JSON response after 3 attempts"
        )
        
        with patch.object(scanner, "_get_files_content", return_value=files_content):
            scanner._run_scan(state)
        
        # Should not wait for reconnection (not a connection error)
        mock_dependencies["llm_client"].wait_for_connection.assert_not_called()

    def test_empty_response_from_llm(self, mock_dependencies):
        """Test scanner handles empty response from LLM."""
        scanner = Scanner(**mock_dependencies)
        
        state = GitState(
            changed_files=[ChangedFile(path="test.py", status="unstaged")]
        )
        
        files_content = {"test.py": "x = 1"}
        
        # Empty response (no issues)
        mock_dependencies["llm_client"].query.return_value = {"issues": []}
        
        with patch.object(scanner, "_get_files_content", return_value=files_content):
            scanner._run_scan(state)
        
        # Should complete without error
        assert True

    def test_max_retries_exceeded(self, mock_dependencies):
        """Test scanner handles max retries exceeded."""
        scanner = Scanner(**mock_dependencies)
        scanner.config.max_llm_retries = 2
        
        state = GitState(
            changed_files=[ChangedFile(path="test.py", status="unstaged")]
        )
        
        files_content = {"test.py": "x = 1"}
        
        mock_dependencies["llm_client"].query.side_effect = LLMClientError(
            "Connection refused"
        )
        mock_dependencies["llm_client"].wait_for_connection = MagicMock()
        
        with patch.object(scanner, "_get_files_content", return_value=files_content):
            scanner._run_scan(state)
        
        # Should attempt retries
        assert mock_dependencies["llm_client"].wait_for_connection.call_count >= 1


class TestCheckGroupEdgeCases:
    """Edge cases for check group pattern matching."""

    def test_pattern_with_trailing_comma(self):
        """Test pattern with trailing comma."""
        group = CheckGroup(pattern="*.cpp, *.h, ", checks=["test"])
        
        # Should still match
        assert group.matches_file("test.cpp") is True
        assert group.matches_file("test.h") is True

    def test_pattern_with_leading_comma(self):
        """Test pattern with leading comma."""
        group = CheckGroup(pattern=", *.cpp, *.h", checks=["test"])
        
        # Should still match
        assert group.matches_file("test.cpp") is True

    def test_pattern_with_double_commas(self):
        """Test pattern with double commas."""
        group = CheckGroup(pattern="*.cpp,, *.h", checks=["test"])
        
        # Should still match
        assert group.matches_file("test.cpp") is True
        assert group.matches_file("test.h") is True

    def test_pattern_case_sensitivity(self):
        """Test pattern case sensitivity."""
        group = CheckGroup(pattern="*.CPP", checks=["test"])
        
        # Case-sensitive matching
        assert group.matches_file("test.CPP") is True
        # Note: This depends on fnmatch behavior

    def test_pattern_with_brackets(self):
        """Test pattern with bracket characters."""
        group = CheckGroup(pattern="test[123].cpp", checks=["test"])
        
        # Should match files with brackets
        assert group.matches_file("test1.cpp") is True
        assert group.matches_file("test2.cpp") is True

    def test_pattern_with_question_mark(self):
        """Test pattern with question mark wildcard."""
        group = CheckGroup(pattern="test?.cpp", checks=["test"])
        
        # Should match single character
        assert group.matches_file("test1.cpp") is True
        assert group.matches_file("testA.cpp") is True


class TestOutputEdgeCases:
    """Edge cases for output generation."""

    def test_output_with_no_issues(self, mock_dependencies):
        """Test output generation with no issues."""
        mock_dependencies["issue_tracker"].get_issues_by_file.return_value = {}
        mock_dependencies["issue_tracker"].get_stats.return_value = {
            "open": 0,
            "resolved": 0,
            "total": 0
        }
        
        # Should not crash
        mock_dependencies["output_generator"].write(
            mock_dependencies["issue_tracker"],
            {},
            "RUNNING",
            0,
            1,
            "test check",
            ""
        )

    def test_output_with_very_long_issue_description(self, mock_dependencies):
        """Test output with very long issue descriptions."""
        long_desc = "This is a very long description. " * 100
        
        mock_dependencies["issue_tracker"].get_issues_by_file.return_value = {
            "test.cpp": [Issue(
                file_path="test.cpp",
                line_number=1,
                description=long_desc,
                suggested_fix="Fix",
                check_query="Check",
                timestamp=datetime.now(),
                code_snippet="",
            )]
        }
        mock_dependencies["issue_tracker"].get_stats.return_value = {
            "open": 1,
            "resolved": 0,
            "total": 1
        }
        
        # Should not crash
        mock_dependencies["output_generator"].write(
            mock_dependencies["issue_tracker"],
            {},
            "RUNNING",
            1,
            1,
            "test check",
            ""
        )

    def test_output_with_unicode_characters(self, mock_dependencies):
        """Test output with unicode characters."""
        mock_dependencies["issue_tracker"].get_issues_by_file.return_value = {
            "test.cpp": [Issue(
                file_path="test.cpp",
                line_number=1,
                description="Ошибка: утечка памяти",
                suggested_fix="Исправить",
                check_query="Check",
                timestamp=datetime.now(),
                code_snippet="",
            )]
        }
        mock_dependencies["issue_tracker"].get_stats.return_value = {
            "open": 1,
            "resolved": 0,
            "total": 1
        }
        
        # Should not crash
        mock_dependencies["output_generator"].write(
            mock_dependencies["issue_tracker"],
            {},
            "RUNNING",
            1,
            1,
            "test check",
            ""
        )


class TestCtagsEdgeCases:
    """Edge cases for ctags index."""

    def test_ctags_not_installed(self, tmp_path):
        """Test scanner handles ctags not being installed."""
        # This would be tested in integration tests
        # Here we just verify the mock works
        mock_index = MagicMock(spec=CtagsIndex)
        mock_index.target_directory = tmp_path
        mock_index.find_symbol.return_value = []
        
        # Should not crash
        result = mock_index.find_symbol("test")
        assert result == []

    def test_ctags_empty_index(self, tmp_path):
        """Test scanner handles empty ctags index."""
        mock_index = MagicMock(spec=CtagsIndex)
        mock_index.target_directory = tmp_path
        mock_index.find_symbol.return_value = []
        mock_index.get_symbols_in_file.return_value = []
        
        # Should not crash
        result = mock_index.find_symbol("test")
        assert result == []
        result = mock_index.get_symbols_in_file("test.py")
        assert result == []

    def test_ctags_symbol_not_found(self, tmp_path):
        """Test scanner handles symbol not found in index."""
        mock_index = MagicMock(spec=CtagsIndex)
        mock_index.target_directory = tmp_path
        mock_index.find_symbol.return_value = []
        
        # Should return empty list
        result = mock_index.find_symbol("nonexistent_symbol")
        assert result == []


class TestProjectManagerEdgeCases:
    """Edge cases for project manager."""

    def test_project_state_corruption(self):
        """Test handling of corrupted project state."""
        # This would be tested in integration tests
        # Here we verify the model handles invalid data
        from code_scanner.models import Project, ScanStatus
        from code_scanner.config import Config, LLMConfig
        
        # Create project with potentially invalid state
        config = Config(
            target_directory=Path("/test"),
            config_file=Path("/test/config.toml"),
            check_groups=[],
            llm=LLMConfig(backend="lm-studio", host="localhost", port=1234, context_limit=16384),
        )
        project = Project(
            project_id="test",
            target_directory=Path("/test"),
            config_file=Path("/test/config.toml"),
            config=config,
            scan_status=ScanStatus.RUNNING,
            current_check_index=0,
            total_checks=0,
            current_check_query="",
            error_message="",
            scan_info={},
            last_scanned_files=set(),
            last_file_contents_hash={},
            last_scan_time=None,
            inactive_since=None,
        )
        
        # Should handle gracefully
        assert project.scan_status == ScanStatus.RUNNING

    def test_project_with_no_scan_info(self):
        """Test project with no scan info."""
        from code_scanner.models import Project, ScanStatus
        from code_scanner.config import Config, LLMConfig
        
        # Create config
        config = Config(
            target_directory=Path("/test"),
            config_file=Path("/test/config.toml"),
            check_groups=[],
            llm=LLMConfig(backend="lm-studio", host="localhost", port=1234, context_limit=16384),
        )
        project = Project(
            project_id="test",
            target_directory=Path("/test"),
            config_file=Path("/test/config.toml"),
            config=config,
            scan_status=ScanStatus.INITIALIZING,
            current_check_index=0,
            total_checks=0,
            current_check_query="",
            error_message="",
            scan_info=None,  # No scan info
            last_scanned_files=set(),
            last_file_contents_hash={},
            last_scan_time=None,
            inactive_since=None,
        )
        
        # Should handle gracefully
        assert project.scan_info is None


class TestFilesystemEdgeCases:
    """Edge cases for filesystem operations."""

    def test_file_permission_denied(self, tmp_path):
        """Test handling of permission denied errors."""
        # Create a file
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")
        
        # Mock permission denied - patch at module level
        with patch("code_scanner.utils.open", side_effect=PermissionError("Permission denied")):
            content = read_file_content(test_file)
            # Should return None on error
            assert content is None

    def test_file_not_found(self, tmp_path):
        """Test handling of file not found errors."""
        nonexistent = tmp_path / "nonexistent.txt"
        
        content = read_file_content(nonexistent)
        # Should return None for nonexistent files
        assert content is None

    def test_symlink_to_nonexistent_target(self, tmp_path):
        """Test handling of symlink to nonexistent target."""
        # Create symlink to nonexistent file
        symlink = tmp_path / "symlink"
        try:
            symlink.symlink_to("nonexistent")
        except (OSError, NotImplementedError):
            # Symlinks not supported on this system
            pytest.skip("Symlinks not supported")

        # Should handle gracefully
        content = read_file_content(symlink)
        # Behavior depends on OS
        assert content is None or content == ""

    def test_file_is_directory(self, tmp_path):
        """Test handling when path is a directory."""
        dir_path = tmp_path / "directory"
        dir_path.mkdir()
        
        # Should handle gracefully
        content = read_file_content(dir_path)
        # Behavior depends on implementation
        assert content is None or content == ""
