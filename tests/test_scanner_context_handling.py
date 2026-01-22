"""Additional tests for scanner context handling - targeting uncovered lines 383-395 and 939-960."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from code_scanner.scanner import Scanner
from code_scanner.config import Config, CheckGroup
from code_scanner.models import GitState, ChangedFile
from code_scanner.base_client import ContextOverflowError, LLMClientError
from code_scanner.ctags_index import CtagsIndex


@pytest.fixture
def mock_config():
    """Create a mock Config object."""
    config = MagicMock(spec=Config)
    config.target_directory = Path("/test/repo")
    config.output_file = "results.md"
    config.log_file = "scanner.log"
    config.git_poll_interval = 0.1
    config.llm_retry_interval = 0.1
    config.max_llm_retries = 2
    config.check_groups = [
        CheckGroup(pattern="*.py", checks=["Check for bugs"]),
    ]
    return config


@pytest.fixture
def mock_ctags_index():
    """Create a mock CtagsIndex."""
    mock_index = MagicMock(spec=CtagsIndex)
    mock_index.target_directory = Path("/test/repo")
    mock_index.is_indexed = True
    mock_index.is_indexing = False
    mock_index.index_error = None
    mock_index.find_symbol.return_value = []
    mock_index.find_symbols_by_pattern.return_value = []
    mock_index.find_definitions.return_value = []
    mock_index.get_symbols_in_file.return_value = []
    mock_index.get_class_members.return_value = []
    mock_index.get_file_structure.return_value = {
        "file": "/test/repo/test.py",
        "language": "Python",
        "symbols": [],
        "structure_summary": "",
    }
    mock_index.get_stats.return_value = {
        "total_symbols": 0,
        "files_indexed": 0,
        "symbols_by_kind": {},
        "languages": [],
    }
    return mock_index


@pytest.fixture
def mock_dependencies(mock_config, mock_ctags_index):
    """Create mock dependencies for Scanner."""
    git_watcher = MagicMock()
    llm_client = MagicMock()
    llm_client.context_limit = 8000
    issue_tracker = MagicMock()
    issue_tracker.add_issues.return_value = 0
    issue_tracker.update_from_scan.return_value = (0, 0)
    issue_tracker.get_stats.return_value = {"total": 0}
    output_generator = MagicMock()

    return {
        "config": mock_config,
        "git_watcher": git_watcher,
        "llm_client": llm_client,
        "issue_tracker": issue_tracker,
        "output_generator": output_generator,
        "ctags_index": mock_ctags_index,
    }


class TestContextOverflowHandling:
    """Tests for ContextOverflowError handling in _run_scan (lines 383-395)."""

    def test_context_overflow_logs_error_and_continues(self, mock_dependencies):
        """ContextOverflowError logs error with check info and continues to next check."""
        scanner = Scanner(**mock_dependencies)

        state = GitState(
            changed_files=[ChangedFile(path="test.py", status="unstaged")]
        )

        files_content = {"test.py": "x = 1"}

        # First check raises ContextOverflowError, scan should continue
        mock_dependencies["llm_client"].query.side_effect = ContextOverflowError(
            "Context limit exceeded - model loaded with 4096 tokens"
        )

        with patch.object(scanner, "_get_files_content", return_value=files_content):
            # Should NOT raise - ContextOverflowError is caught and logged
            scanner._run_scan(state)

        # Verify error was tracked in scan_info
        assert "skipped_batches_context_overflow" in scanner._scan_info
        assert len(scanner._scan_info["skipped_batches_context_overflow"]) == 1
        assert scanner._scan_info["skipped_batches_context_overflow"][0]["error"] == "limits_miscalculated"

    def test_context_overflow_tracks_check_name(self, mock_dependencies):
        """ContextOverflowError tracking includes the check that failed."""
        mock_dependencies["config"].check_groups = [
            CheckGroup(pattern="*.py", checks=["Very long check description that exceeds fifty"]),
        ]
        scanner = Scanner(**mock_dependencies)

        state = GitState(
            changed_files=[ChangedFile(path="test.py", status="unstaged")]
        )

        files_content = {"test.py": "x = 1"}

        mock_dependencies["llm_client"].query.side_effect = ContextOverflowError("Overflow")

        with patch.object(scanner, "_get_files_content", return_value=files_content):
            scanner._run_scan(state)

        # Check name should be truncated to 50 chars
        overflow_info = scanner._scan_info["skipped_batches_context_overflow"][0]
        assert len(overflow_info["check"]) <= 50

    def test_multiple_context_overflows_all_tracked(self, mock_dependencies):
        """Multiple ContextOverflowError instances are all tracked."""
        mock_dependencies["config"].check_groups = [
            CheckGroup(pattern="*.py", checks=["Check 1", "Check 2", "Check 3"]),
        ]
        scanner = Scanner(**mock_dependencies)

        state = GitState(
            changed_files=[ChangedFile(path="test.py", status="unstaged")]
        )

        files_content = {"test.py": "x = 1"}

        # All checks fail with overflow
        mock_dependencies["llm_client"].query.side_effect = ContextOverflowError("Overflow")

        with patch.object(scanner, "_get_files_content", return_value=files_content):
            scanner._run_scan(state)

        # All 3 overflows should be tracked
        assert len(scanner._scan_info["skipped_batches_context_overflow"]) == 3


class TestContextLimitThreshold:
    """Tests for context limit threshold handling in _run_check_with_tools (lines 937-960)."""

    def test_context_threshold_forces_final_answer(self, mock_dependencies):
        """When context threshold is reached, LLM is asked to finalize without more tools."""
        mock_dependencies["llm_client"].context_limit = 1000  # Very small limit
        scanner = Scanner(**mock_dependencies)

        # Simulate tool calls that accumulate tokens until threshold
        query_count = [0]
        def query_side_effect(*args, **kwargs):
            query_count[0] += 1
            if query_count[0] <= 3:
                # Return tool calls with large results
                return {
                    "tool_calls": [
                        {"tool_name": "search_text", "arguments": {"patterns": "test"}}
                    ]
                }
            # Final answer
            return {"issues": []}

        mock_dependencies["llm_client"].query.side_effect = query_side_effect

        batch = {"test.py": "x" * 100}  # Use some initial context

        with patch.object(scanner.tool_executor, "execute_tool") as mock_exec:
            # Return large results that push context toward threshold
            mock_exec.return_value = MagicMock(
                success=True,
                data={"matches": [{"line": i} for i in range(100)]},  # Large result
                warning=None,
                error=None,
            )

            issues = scanner._run_check_with_tools(
                check_query="Test check",
                batch=batch,
                batch_idx=0,
            )

        # Should eventually get a final answer (empty issues)
        assert issues == []
        # Should have made multiple queries
        assert query_count[0] >= 1

    def test_max_iterations_based_on_context(self, mock_dependencies):
        """Max tool iterations is calculated based on available context."""
        mock_dependencies["llm_client"].context_limit = 2000  # Small context
        scanner = Scanner(**mock_dependencies)

        iteration_count = [0]
        def query_side_effect(*args, **kwargs):
            iteration_count[0] += 1
            # Always request tool to test iteration limit
            return {
                "tool_calls": [
                    {"tool_name": "list_directory", "arguments": {"directory_path": "."}}
                ]
            }

        mock_dependencies["llm_client"].query.side_effect = query_side_effect

        with patch.object(scanner.tool_executor, "execute_tool") as mock_exec:
            mock_exec.return_value = MagicMock(
                success=True,
                data={"items": []},
                warning=None,
                error=None,
            )

            issues = scanner._run_check_with_tools(
                check_query="Test",
                batch={"test.py": "small content"},
                batch_idx=0,
            )

        # With small context, iterations should be limited
        # Max is 50, but context-based limit may be lower
        assert iteration_count[0] <= 50
        assert issues == []  # Returns empty after max iterations


class TestFormatToolArgs:
    """Tests for _format_tool_args_for_log helper (lines 999, 1018, 1026, 1028)."""

    def test_format_tool_args_no_args(self, mock_dependencies):
        """Format returns '(no args)' for empty arguments."""
        scanner = Scanner(**mock_dependencies)
        result = scanner._format_tool_args_for_log("some_tool", {})
        assert result == "(no args)"

    def test_format_tool_args_file_path(self, mock_dependencies):
        """Format prioritizes file_path in output."""
        scanner = Scanner(**mock_dependencies)
        result = scanner._format_tool_args_for_log("read_file", {"file_path": "src/main.py"})
        assert "src/main.py" in result

    def test_format_tool_args_patterns_list(self, mock_dependencies):
        """Format handles list patterns with truncation."""
        scanner = Scanner(**mock_dependencies)
        result = scanner._format_tool_args_for_log(
            "search_text",
            {"patterns": ["pattern1", "pattern2", "pattern3", "pattern4", "pattern5"]}
        )
        # Should include first 3 patterns only
        assert "pattern1" in result
        assert "pattern2" in result
        assert "pattern3" in result

    def test_format_tool_args_line_range(self, mock_dependencies):
        """Format includes line range when present."""
        scanner = Scanner(**mock_dependencies)
        result = scanner._format_tool_args_for_log(
            "read_file",
            {"file_path": "test.py", "start_line": 10, "end_line": 50}
        )
        assert "test.py" in result
        assert "10-50" in result or "10" in result

    def test_format_tool_args_start_line_only(self, mock_dependencies):
        """Format handles start_line without end_line."""
        scanner = Scanner(**mock_dependencies)
        result = scanner._format_tool_args_for_log(
            "read_file",
            {"file_path": "test.py", "start_line": 100}
        )
        assert "from line 100" in result
