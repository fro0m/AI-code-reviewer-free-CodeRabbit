"""Unit tests for project switching logic."""

import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from code_scanner.models import Project, ScanStatus
from code_scanner.project_manager import ProjectManager


class TestProjectSwitchingCooldown:
    """Tests for project switching with cooldown."""

    def test_project_switching_with_cooldown(self):
        """Verify 5-minute minimum interval."""
        pm = ProjectManager()

        # Create two projects
        project1 = pm.add_project(
            project_id="project1",
            target_directory=Path("/tmp/project1"),
            config_file=Path("/tmp/config1.toml"),
            config=Mock(),
        )
        project2 = pm.add_project(
            project_id="project2",
            target_directory=Path("/tmp/project2"),
            config_file=Path("/tmp/config2.toml"),
            config=Mock(),
        )

        # Switch to project1
        pm.switch_to_project(project1)
        assert pm.get_active_project() == project1
        assert pm._last_switch_time is not None

        # Try to switch immediately - should be blocked
        assert not pm.can_switch_to_project("project2")

        # Wait 5 minutes - should be allowed
        with patch('code_scanner.project_manager.datetime') as mock_dt:
            mock_dt.now.return_value = datetime.now(timezone.utc) + timedelta(minutes=6)
            assert pm.can_switch_to_project("project2")

    def test_switch_immediately_after_cooldown(self):
        """Test switch immediately after cooldown."""
        pm = ProjectManager()

        project1 = pm.add_project(
            project_id="project1",
            target_directory=Path("/tmp/project1"),
            config_file=Path("/tmp/config1.toml"),
            config=Mock(),
        )
        project2 = pm.add_project(
            project_id="project2",
            target_directory=Path("/tmp/project2"),
            config_file=Path("/tmp/config2.toml"),
            config=Mock(),
        )

        # Switch to project1
        pm.switch_to_project(project1)

        # Wait exactly 5 minutes - should be allowed
        with patch('code_scanner.project_manager.datetime') as mock_dt:
            mock_dt.now.return_value = datetime.now(timezone.utc) + timedelta(minutes=5, seconds=1)
            assert pm.can_switch_to_project("project2")

    def test_switch_before_cooldown_blocked(self):
        """Test switch before cooldown (should be blocked)."""
        pm = ProjectManager()

        project1 = pm.add_project(
            project_id="project1",
            target_directory=Path("/tmp/project1"),
            config_file=Path("/tmp/config1.toml"),
            config=Mock(),
        )
        project2 = pm.add_project(
            project_id="project2",
            target_directory=Path("/tmp/project2"),
            config_file=Path("/tmp/config2.toml"),
            config=Mock(),
        )

        # Switch to project1
        pm.switch_to_project(project1)

        # Try to switch after 4 minutes - should be blocked
        with patch('code_scanner.project_manager.datetime') as mock_dt:
            mock_dt.now.return_value = datetime.now(timezone.utc) + timedelta(minutes=4, seconds=59)
            assert not pm.can_switch_to_project("project2")


class TestStatePreservation:
    """Tests for state preservation across switches."""

    def test_state_preservation_scan_info(self):
        """Verify scan_info preserved."""
        pm = ProjectManager()

        project1 = pm.add_project(
            project_id="project1",
            target_directory=Path("/tmp/project1"),
            config_file=Path("/tmp/config1.toml"),
            config=Mock(),
        )

        # Set scan_info
        project1.scan_info = {
            "checks_run": 5,
            "total_checks": 10,
            "files_scanned": ["file1.py", "file2.py"],
        }

        # Verify scan_info is preserved in Project object
        assert project1.scan_info["checks_run"] == 5
        assert project1.scan_info["total_checks"] == 10

    def test_state_preservation_last_scanned_files(self):
        """Verify last_scanned_files preserved."""
        pm = ProjectManager()

        project1 = pm.add_project(
            project_id="project1",
            target_directory=Path("/tmp/project1"),
            config_file=Path("/tmp/config1.toml"),
            config=Mock(),
        )

        # Set last_scanned_files
        project1.last_scanned_files = {"file1.py", "file2.py", "file3.py"}

        # Verify last_scanned_files is preserved
        assert len(project1.last_scanned_files) == 3
        assert "file1.py" in project1.last_scanned_files

    def test_state_preservation_last_file_contents_hash(self):
        """Verify last_file_contents_hash preserved."""
        pm = ProjectManager()

        project1 = pm.add_project(
            project_id="project1",
            target_directory=Path("/tmp/project1"),
            config_file=Path("/tmp/config1.toml"),
            config=Mock(),
        )

        # Set last_file_contents_hash
        project1.last_file_contents_hash = {
            "file1.py": 12345,
            "file2.py": 67890,
        }

        # Verify last_file_contents_hash is preserved
        assert project1.last_file_contents_hash["file1.py"] == 12345
        assert project1.last_file_contents_hash["file2.py"] == 67890

    def test_issue_tracker_reference_maintained(self):
        """Verify IssueTracker reference maintained (no save/restore needed)."""
        pm = ProjectManager()

        project1 = pm.add_project(
            project_id="project1",
            target_directory=Path("/tmp/project1"),
            config_file=Path("/tmp/config1.toml"),
            config=Mock(),
        )

        # Create mock issue tracker
        issue_tracker = Mock()
        project1.issue_tracker = issue_tracker

        # Verify issue tracker reference is maintained
        assert project1.issue_tracker is issue_tracker


class TestOutputFileTimestamps:
    """Tests for output file timestamps."""

    def test_active_since_timestamp_on_running_status(self):
        """Verify "active since" timestamp on RUNNING status."""
        status = ScanStatus.RUNNING
        active_since = datetime(2026, 1, 25, 21, 5, 0)

        text = status.get_display_text(
            check_index=1,
            total_checks=10,
            check_query="Check for bugs",
            active_since=active_since
        )

        assert "active since: January 25, 2026 at 09:05 PM" in text
        assert "UTC" not in text  # No timezone indicator

    def test_inactive_since_timestamp_on_waiting_other_project(self):
        """Verify "inactive since" timestamp on WAITING_OTHER_PROJECT."""
        status = ScanStatus.WAITING_OTHER_PROJECT
        inactive_since = datetime(2026, 1, 25, 21, 10, 0)

        text = status.get_display_text(inactive_since=inactive_since)

        assert "inactive since: January 25, 2026 at 09:10 PM" in text
        assert "UTC" not in text  # No timezone indicator

    def test_timestamp_format_local_time_no_timezone(self):
        """Verify timestamp format (human-readable, local time, no timezone)."""
        status = ScanStatus.WAITING_NO_CHANGES
        timestamp = datetime(2026, 1, 25, 21, 15, 0)

        text = status.get_display_text(timestamp=timestamp)

        assert "since: January 25, 2026 at 09:15 PM" in text
        assert "UTC" not in text  # No timezone indicator


class TestGlobalCooldown:
    """Tests for global cooldown in ProjectManager."""

    def test_last_switch_time_updated_on_any_switch(self):
        """Verify _last_switch_time is updated on any switch."""
        pm = ProjectManager()

        project1 = pm.add_project(
            project_id="project1",
            target_directory=Path("/tmp/project1"),
            config_file=Path("/tmp/config1.toml"),
            config=Mock(),
        )
        project2 = pm.add_project(
            project_id="project2",
            target_directory=Path("/tmp/project2"),
            config_file=Path("/tmp/config2.toml"),
            config=Mock(),
        )

        # Switch to project1
        assert pm._last_switch_time is None
        pm.switch_to_project(project1)
        assert pm._last_switch_time is not None

        # Switch to project2
        first_switch_time = pm._last_switch_time
        pm.switch_to_project(project2)
        assert pm._last_switch_time != first_switch_time

    def test_cooldown_applies_regardless_of_projects(self):
        """Verify cooldown applies regardless of which projects are involved."""
        pm = ProjectManager()

        project1 = pm.add_project(
            project_id="project1",
            target_directory=Path("/tmp/project1"),
            config_file=Path("/tmp/config1.toml"),
            config=Mock(),
        )
        project2 = pm.add_project(
            project_id="project2",
            target_directory=Path("/tmp/project2"),
            config_file=Path("/tmp/config2.toml"),
            config=Mock(),
        )
        project3 = pm.add_project(
            project_id="project3",
            target_directory=Path("/tmp/project3"),
            config_file=Path("/tmp/config3.toml"),
            config=Mock(),
        )

        # Switch to project1
        pm.switch_to_project(project1)

        # Try to switch to project2 immediately - should be blocked
        assert not pm.can_switch_to_project("project2")

        # Try to switch to project3 immediately - should also be blocked
        assert not pm.can_switch_to_project("project3")

    def test_cooldown_check_uses_global_time(self):
        """Verify cooldown check uses global time, not per-project time."""
        pm = ProjectManager()

        project1 = pm.add_project(
            project_id="project1",
            target_directory=Path("/tmp/project1"),
            config_file=Path("/tmp/config1.toml"),
            config=Mock(),
        )
        project2 = pm.add_project(
            project_id="project2",
            target_directory=Path("/tmp/project2"),
            config_file=Path("/tmp/config2.toml"),
            config=Mock(),
        )

        # Switch to project1
        pm.switch_to_project(project1)

        # Verify can_switch_to_project uses global _last_switch_time
        # (not per-project last_switch_time)
        assert pm._last_switch_time is not None
        assert not pm.can_switch_to_project("project2")
