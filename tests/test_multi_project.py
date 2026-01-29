"""Integration tests for multi-project workflows."""

import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from code_scanner.models import Project, ScanStatus
from code_scanner.project_manager import ProjectManager


class TestFullMultiProjectWorkflow:
    """Tests for full multi-project workflow."""

    def test_full_multi_project_workflow(self):
        """Startup with 3 projects, scan A, switch B, switch C, verify states."""
        pm = ProjectManager()

        # Create 3 projects
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
        assert pm.get_active_project() == project1
        assert project1.scan_status == ScanStatus.RUNNING
        assert project1.is_active is True

        # Verify state preserved
        project1.scan_info = {"checks_run": 5}
        project1.last_scanned_files = {"file1.py"}
        project1.last_file_contents_hash = {"file1.py": 12345}

        assert project1.scan_info["checks_run"] == 5
        assert "file1.py" in project1.last_scanned_files

        # Switch to project2
        pm.switch_to_project(project2)
        assert pm.get_active_project() == project2
        assert project1.scan_status == ScanStatus.WAITING_OTHER_PROJECT
        assert project1.is_active is False
        assert project1.inactive_since is not None
        assert project2.scan_status == ScanStatus.RUNNING
        assert project2.is_active is True

        # Verify project1 state preserved
        assert project1.scan_info["checks_run"] == 5
        assert "file1.py" in project1.last_scanned_files

        # Switch to project3
        pm.switch_to_project(project3)
        assert pm.get_active_project() == project3
        assert project2.scan_status == ScanStatus.WAITING_OTHER_PROJECT
        assert project3.scan_status == ScanStatus.RUNNING

    def test_determine_active_project_with_multiple_projects(self):
        """Test determine_active_project with multiple projects."""
        pm = ProjectManager()

        # Create 3 projects
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

        # Mock git watchers with different activity levels
        now = datetime.now(timezone.utc)

        mock_git1 = Mock()
        mock_state1 = Mock()
        mock_state1.has_changes = True
        mock_state1.changed_files = [
            Mock(mtime_ns=(now - timedelta(minutes=30)).timestamp() * 1e9)
        ]
        mock_git1.get_state.return_value = mock_state1
        project1.git_watcher = mock_git1

        mock_git2 = Mock()
        mock_state2 = Mock()
        mock_state2.has_changes = True
        mock_state2.changed_files = [
            Mock(mtime_ns=(now - timedelta(minutes=10)).timestamp() * 1e9)
        ]
        mock_git2.get_state.return_value = mock_state2
        project2.git_watcher = mock_git2

        mock_git3 = Mock()
        mock_state3 = Mock()
        mock_state3.has_changes = True
        mock_state3.changed_files = [
            Mock(mtime_ns=(now - timedelta(minutes=20)).timestamp() * 1e9)
        ]
        mock_git3.get_state.return_value = mock_state3
        project3.git_watcher = mock_git3

        # Determine active project - should select project2 (most recent changes)
        active = pm.determine_active_project()
        assert active == project2


class TestProjectSwitchingDuringScan:
    """Tests for project switching during scan."""

    def test_project_switching_during_scan(self):
        """Start scanning project A, make changes to B, switch after check."""
        pm = ProjectManager()

        # Create 2 projects
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

        # Switch to project1 (simulating start of scan)
        pm.switch_to_project(project1)
        assert pm.get_active_project() == project1

        # Mock project1 with no changes
        mock_git1 = Mock()
        mock_state1 = Mock()
        mock_state1.has_changes = False
        mock_state1.changed_files = []
        mock_git1.get_state.return_value = mock_state1
        project1.git_watcher = mock_git1

        # Mock project2 with changes
        now = datetime.now(timezone.utc)

        mock_git2 = Mock()
        mock_state2 = Mock()
        mock_state2.has_changes = True
        mock_state2.changed_files = [
            Mock(mtime_ns=now.timestamp() * 1e9)
        ]
        mock_git2.get_state.return_value = mock_state2
        project2.git_watcher = mock_git2

        # Determine active project - should select project2 (has changes)
        active = pm.determine_active_project()
        assert active == project2


class TestCooldownWithMultipleChanges:
    """Tests for cooldown with multiple changes."""

    def test_cooldown_with_multiple_changes(self):
        """Change A, change B 1 min later, no switch. Change C 6 min later, switch."""
        pm = ProjectManager()

        # Create 3 projects
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

        # Mock project2 with changes 1 minute later
        now = datetime.now(timezone.utc)

        mock_git2 = Mock()
        mock_state2 = Mock()
        mock_state2.has_changes = True
        mock_state2.changed_files = [
            Mock(mtime_ns=(now - timedelta(minutes=1)).timestamp() * 1e9)
        ]
        mock_git2.get_state.return_value = mock_state2
        project2.git_watcher = mock_git2

        # Try to switch - should be blocked (cooldown not met)
        assert not pm.can_switch_to_project("project2")

        # Mock project3 with changes 6 minutes later
        mock_git3 = Mock()
        mock_state3 = Mock()
        mock_state3.has_changes = True
        mock_state3.changed_files = [
            Mock(mtime_ns=(now - timedelta(minutes=6)).timestamp() * 1e9)
        ]
        mock_git3.get_state.return_value = mock_state3
        project3.git_watcher = mock_git3

        # Try to switch - should be allowed (cooldown met)
        with patch('code_scanner.project_manager.datetime') as mock_dt:
            mock_dt.now.return_value = now + timedelta(minutes=6)
            assert pm.can_switch_to_project("project3")


class TestLongRunningScanner:
    """Tests for long-running scanner."""

    def test_long_running_scanner_state_consistency(self):
        """Verify state consistency over multiple switches."""
        pm = ProjectManager()

        # Create 2 projects
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

        # Set initial state
        project1.scan_info = {"checks_run": 10}
        project1.last_scanned_files = {"file1.py", "file2.py"}
        project1.last_file_contents_hash = {"file1.py": 11111, "file2.py": 22222}

        # Switch back and forth multiple times
        for i in range(3):
            pm.switch_to_project(project1)
            assert project1.scan_info["checks_run"] == 10
            assert len(project1.last_scanned_files) == 2
            assert project1.last_file_contents_hash["file1.py"] == 11111

            pm.switch_to_project(project2)
            assert project1.scan_info["checks_run"] == 10
            assert len(project1.last_scanned_files) == 2
            assert project1.last_file_contents_hash["file1.py"] == 11111

        # Verify state preserved after multiple switches
        assert project1.scan_info["checks_run"] == 10
        assert len(project1.last_scanned_files) == 2
        assert project1.last_file_contents_hash["file1.py"] == 11111
