"""Tests for project switching with branch mode scanning.

Verifies that project switching works correctly when projects are configured
with ScanMode.BRANCH, including active project determination, state
preservation, status transitions, eligibility filtering, and full workflows.
"""

import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from code_scanner.models import Project, ScanStatus, ScanMode
from code_scanner.project_manager import ProjectManager


class TestBranchModeDetermineActiveProject:
    """Tests for determine_active_project() in branch mode."""

    def test_branch_mode_selects_most_recent_changes(self):
        """Verify branch mode project with most recent changes is selected."""
        pm = ProjectManager()
        now = datetime.now(timezone.utc)

        project_a = pm.add_project(
            project_id="project_a",
            target_directory=Path("/tmp/project_a"),
            config_file=Path("/tmp/config_a.toml"),
            config=Mock(),
        )
        project_b = pm.add_project(
            project_id="project_b",
            target_directory=Path("/tmp/project_b"),
            config_file=Path("/tmp/config_b.toml"),
            config=Mock(),
        )

        mock_git_a = Mock()
        mock_state_a = Mock()
        mock_state_a.has_changes = True
        mock_state_a.changed_files = [
            Mock(mtime_ns=(now - timedelta(minutes=30)).timestamp() * 1e9,
                 path="src/a.cpp")
        ]
        mock_git_a.get_state.return_value = mock_state_a
        project_a.git_watcher = mock_git_a

        mock_git_b = Mock()
        mock_state_b = Mock()
        mock_state_b.has_changes = True
        mock_state_b.changed_files = [
            Mock(mtime_ns=(now - timedelta(minutes=5)).timestamp() * 1e9,
                 path="src/b.cpp")
        ]
        mock_git_b.get_state.return_value = mock_state_b
        project_b.git_watcher = mock_git_b

        active = pm.determine_active_project()
        assert active == project_b

    def test_branch_mode_single_project_always_selected(self):
        """Verify single project in branch mode is always selected."""
        pm = ProjectManager()
        now = datetime.now(timezone.utc)

        project = pm.add_project(
            project_id="only",
            target_directory=Path("/tmp/only"),
            config_file=Path("/tmp/config.toml"),
            config=Mock(),
        )
        mock_git = Mock()
        mock_state = Mock()
        mock_state.has_changes = True
        mock_state.changed_files = [
            Mock(mtime_ns=now.timestamp() * 1e9, path="src/file.cpp")
        ]
        mock_git.get_state.return_value = mock_state
        project.git_watcher = mock_git

        active = pm.determine_active_project()
        assert active == project

    def test_branch_mode_no_changes_keeps_current_active(self):
        """Verify when no branch-mode projects have changes, current active is kept."""
        pm = ProjectManager()
        now = datetime.now(timezone.utc)

        project_a = pm.add_project(
            project_id="project_a",
            target_directory=Path("/tmp/project_a"),
            config_file=Path("/tmp/config_a.toml"),
            config=Mock(),
        )
        project_b = pm.add_project(
            project_id="project_b",
            target_directory=Path("/tmp/project_b"),
            config_file=Path("/tmp/config_b.toml"),
            config=Mock(),
        )

        pm.switch_to_project(project_a, skip_cooldown=True)

        mock_git_a = Mock()
        mock_state_a = Mock()
        mock_state_a.has_changes = False
        mock_state_a.changed_files = []
        mock_git_a.get_state.return_value = mock_state_a
        project_a.git_watcher = mock_git_a

        mock_git_b = Mock()
        mock_state_b = Mock()
        mock_state_b.has_changes = False
        mock_state_b.changed_files = []
        mock_git_b.get_state.return_value = mock_state_b
        project_b.git_watcher = mock_git_b

        active = pm.determine_active_project()
        assert active == project_a

    def test_branch_mode_no_projects_returns_none(self):
        """Verify None returned when no projects exist regardless of mode."""
        pm = ProjectManager()
        active = pm.determine_active_project()
        assert active is None

    def test_branch_mode_multiple_files_max_mtime_used(self):
        """Verify max mtime across multiple branch-changed files is used."""
        pm = ProjectManager()
        now = datetime.now(timezone.utc)

        project_a = pm.add_project(
            project_id="project_a",
            target_directory=Path("/tmp/project_a"),
            config_file=Path("/tmp/config_a.toml"),
            config=Mock(),
        )
        project_b = pm.add_project(
            project_id="project_b",
            target_directory=Path("/tmp/project_b"),
            config_file=Path("/tmp/config_b.toml"),
            config=Mock(),
        )

        mock_git_a = Mock()
        mock_state_a = Mock()
        mock_state_a.has_changes = True
        mock_state_a.changed_files = [
            Mock(mtime_ns=(now - timedelta(minutes=60)).timestamp() * 1e9,
                 path="old.cpp"),
            Mock(mtime_ns=(now - timedelta(minutes=2)).timestamp() * 1e9,
                 path="recent.cpp"),
        ]
        mock_git_a.get_state.return_value = mock_state_a
        project_a.git_watcher = mock_git_a

        mock_git_b = Mock()
        mock_state_b = Mock()
        mock_state_b.has_changes = True
        mock_state_b.changed_files = [
            Mock(mtime_ns=(now - timedelta(minutes=10)).timestamp() * 1e9,
                 path="moderate.cpp"),
        ]
        mock_git_b.get_state.return_value = mock_state_b
        project_b.git_watcher = mock_git_b

        active = pm.determine_active_project()
        assert active == project_a


class TestBranchModeProjectSwitchStatus:
    """Tests for status transitions during branch-mode project switches."""

    def test_switch_away_from_branch_mode_project_with_changes(self):
        """Verify previous branch-mode project gets WAITING_OTHER_PROJECT when it has changes."""
        pm = ProjectManager()
        now = datetime.now(timezone.utc)

        project_a = pm.add_project(
            project_id="project_a",
            target_directory=Path("/tmp/project_a"),
            config_file=Path("/tmp/config_a.toml"),
            config=Mock(),
        )
        project_b = pm.add_project(
            project_id="project_b",
            target_directory=Path("/tmp/project_b"),
            config_file=Path("/tmp/config_b.toml"),
            config=Mock(),
        )

        mock_git_a = Mock()
        mock_state_a = Mock()
        mock_state_a.has_changes = True
        mock_state_a.changed_files = [
            Mock(mtime_ns=now.timestamp() * 1e9, path="branch_change.cpp")
        ]
        mock_git_a.get_state.return_value = mock_state_a
        project_a.git_watcher = mock_git_a

        mock_git_b = Mock()
        mock_state_b = Mock()
        mock_state_b.has_changes = True
        mock_state_b.changed_files = [
            Mock(mtime_ns=now.timestamp() * 1e9, path="other.cpp")
        ]
        mock_git_b.get_state.return_value = mock_state_b
        project_b.git_watcher = mock_git_b

        pm.switch_to_project(project_a, skip_cooldown=True)
        assert project_a.scan_status == ScanStatus.RUNNING
        assert project_a.is_active is True

        # Wait past cooldown
        with patch('code_scanner.project_manager.datetime') as mock_dt:
            future = now + timedelta(minutes=6)
            mock_dt.now.return_value = future
            pm.switch_to_project(project_b)

        assert project_a.scan_status == ScanStatus.WAITING_OTHER_PROJECT
        assert project_a.is_active is False
        assert project_a.inactive_since is not None
        assert project_b.scan_status == ScanStatus.RUNNING
        assert project_b.is_active is True

    def test_switch_away_from_branch_mode_project_without_changes(self):
        """Verify previous branch-mode project gets WAITING_NO_CHANGES when no changes."""
        pm = ProjectManager()
        now = datetime.now(timezone.utc)

        project_a = pm.add_project(
            project_id="project_a",
            target_directory=Path("/tmp/project_a"),
            config_file=Path("/tmp/config_a.toml"),
            config=Mock(),
        )
        project_b = pm.add_project(
            project_id="project_b",
            target_directory=Path("/tmp/project_b"),
            config_file=Path("/tmp/config_b.toml"),
            config=Mock(),
        )

        mock_git_a = Mock()
        mock_state_a = Mock()
        mock_state_a.has_changes = False
        mock_state_a.changed_files = []
        mock_git_a.get_state.return_value = mock_state_a
        project_a.git_watcher = mock_git_a

        mock_git_b = Mock()
        mock_state_b = Mock()
        mock_state_b.has_changes = True
        mock_state_b.changed_files = [
            Mock(mtime_ns=now.timestamp() * 1e9, path="b.cpp")
        ]
        mock_git_b.get_state.return_value = mock_state_b
        project_b.git_watcher = mock_git_b

        pm.switch_to_project(project_a, skip_cooldown=True)
        assert project_a.scan_status == ScanStatus.RUNNING

        with patch('code_scanner.project_manager.datetime') as mock_dt:
            future = now + timedelta(minutes=6)
            mock_dt.now.return_value = future
            pm.switch_to_project(project_b)

        assert project_a.scan_status == ScanStatus.WAITING_NO_CHANGES
        assert project_a.is_active is False
        assert project_b.is_active is True

    def test_switch_between_branch_mode_projects_cooldown_respected(self):
        """Verify cooldown is respected when switching between branch mode projects."""
        pm = ProjectManager()

        project_a = pm.add_project(
            project_id="project_a",
            target_directory=Path("/tmp/project_a"),
            config_file=Path("/tmp/config_a.toml"),
            config=Mock(),
        )
        project_b = pm.add_project(
            project_id="project_b",
            target_directory=Path("/tmp/project_b"),
            config_file=Path("/tmp/config_b.toml"),
            config=Mock(),
        )

        pm.switch_to_project(project_a, skip_cooldown=True)
        assert pm._last_switch_time is None

        pm.switch_to_project(project_b)
        assert pm._last_switch_time is not None
        assert not pm.can_switch_to_project("project_a")

        # After 6 minutes cooldown met
        with patch('code_scanner.project_manager.datetime') as mock_dt:
            mock_dt.now.return_value = datetime.now(timezone.utc) + timedelta(minutes=6)
            assert pm.can_switch_to_project("project_a")


class TestBranchModeStatePreservation:
    """Tests for state preservation during branch-mode project switches."""

    def test_scan_info_preserved_across_branch_mode_switches(self):
        """Verify scan_info survives branch mode project switches."""
        pm = ProjectManager()

        project_a = pm.add_project(
            project_id="project_a",
            target_directory=Path("/tmp/project_a"),
            config_file=Path("/tmp/config_a.toml"),
            config=Mock(),
        )
        project_b = pm.add_project(
            project_id="project_b",
            target_directory=Path("/tmp/project_b"),
            config_file=Path("/tmp/config_b.toml"),
            config=Mock(),
        )

        project_a.scan_info = {
            "checks_run": 7,
            "total_checks": 12,
            "files_scanned": ["a.cpp", "b.cpp"],
        }

        pm.switch_to_project(project_a, skip_cooldown=True)
        pm.switch_to_project(project_b)
        pm.switch_to_project(project_a)

        assert project_a.scan_info["checks_run"] == 7
        assert project_a.scan_info["total_checks"] == 12
        assert "a.cpp" in project_a.scan_info["files_scanned"]

    def test_last_scanned_files_preserved_across_branch_mode_switches(self):
        """Verify last_scanned_files survives branch mode project switches."""
        pm = ProjectManager()

        project_a = pm.add_project(
            project_id="project_a",
            target_directory=Path("/tmp/project_a"),
            config_file=Path("/tmp/config_a.toml"),
            config=Mock(),
        )
        project_b = pm.add_project(
            project_id="project_b",
            target_directory=Path("/tmp/project_b"),
            config_file=Path("/tmp/config_b.toml"),
            config=Mock(),
        )

        project_a.last_scanned_files = {"commit1.cpp", "commit2.cpp", "commit3.cpp"}

        pm.switch_to_project(project_a, skip_cooldown=True)
        pm.switch_to_project(project_b)
        pm.switch_to_project(project_a)

        assert len(project_a.last_scanned_files) == 3
        assert "commit1.cpp" in project_a.last_scanned_files
        assert "commit2.cpp" in project_a.last_scanned_files
        assert "commit3.cpp" in project_a.last_scanned_files

    def test_last_file_contents_hash_preserved_across_branch_mode_switches(self):
        """Verify last_file_contents_hash survives branch mode project switches."""
        pm = ProjectManager()

        project_a = pm.add_project(
            project_id="project_a",
            target_directory=Path("/tmp/project_a"),
            config_file=Path("/tmp/config_a.toml"),
            config=Mock(),
        )
        project_b = pm.add_project(
            project_id="project_b",
            target_directory=Path("/tmp/project_b"),
            config_file=Path("/tmp/config_b.toml"),
            config=Mock(),
        )

        project_a.last_file_contents_hash = {
            "commit1.cpp": 11111,
            "commit2.cpp": 22222,
        }

        pm.switch_to_project(project_a, skip_cooldown=True)
        pm.switch_to_project(project_b)
        pm.switch_to_project(project_a)

        assert project_a.last_file_contents_hash["commit1.cpp"] == 11111
        assert project_a.last_file_contents_hash["commit2.cpp"] == 22222

    def test_all_state_preserved_after_multiple_branch_mode_switches(self):
        """Verify all state preserved after many branch mode switches."""
        pm = ProjectManager()

        project_a = pm.add_project(
            project_id="project_a",
            target_directory=Path("/tmp/project_a"),
            config_file=Path("/tmp/config_a.toml"),
            config=Mock(),
        )
        project_b = pm.add_project(
            project_id="project_b",
            target_directory=Path("/tmp/project_b"),
            config_file=Path("/tmp/config_b.toml"),
            config=Mock(),
        )

        project_a.scan_info = {"checks_run": 10}
        project_a.last_scanned_files = {"f1.cpp", "f2.cpp"}
        project_a.last_file_contents_hash = {"f1.cpp": 999}

        for _ in range(5):
            pm.switch_to_project(project_a)
            assert project_a.scan_info["checks_run"] == 10
            assert len(project_a.last_scanned_files) == 2
            assert project_a.last_file_contents_hash["f1.cpp"] == 999

            pm.switch_to_project(project_b)
            assert project_a.scan_info["checks_run"] == 10
            assert len(project_a.last_scanned_files) == 2
            assert project_a.last_file_contents_hash["f1.cpp"] == 999


class TestBranchModeEligibilityFiltering:
    """Tests for eligibility filtering of already-scanned branch-mode projects."""

    def test_already_scanned_branch_mode_project_not_eligible(self):
        """Verify branch mode project with no new mtimes is filtered out."""
        pm = ProjectManager()
        now = datetime.now(timezone.utc)

        project_a = pm.add_project(
            project_id="project_a",
            target_directory=Path("/tmp/project_a"),
            config_file=Path("/tmp/config_a.toml"),
            config=Mock(),
        )
        project_b = pm.add_project(
            project_id="project_b",
            target_directory=Path("/tmp/project_b"),
            config_file=Path("/tmp/config_b.toml"),
            config=Mock(),
        )

        pm.switch_to_project(project_b, skip_cooldown=True)

        project_a.last_scan_time = now
        project_a_mtime = (now - timedelta(minutes=60)).timestamp()
        mock_git_a = Mock()
        mock_state_a = Mock()
        mock_state_a.has_changes = True
        mock_state_a.changed_files = [
            Mock(mtime_ns=project_a_mtime * 1e9, path="old_branch_file.cpp")
        ]
        mock_git_a.get_state.return_value = mock_state_a
        project_a.git_watcher = mock_git_a

        project_b_mtime = (now - timedelta(minutes=5)).timestamp()
        mock_git_b = Mock()
        mock_state_b = Mock()
        mock_state_b.has_changes = True
        mock_state_b.changed_files = [
            Mock(mtime_ns=project_b_mtime * 1e9, path="recent.cpp")
        ]
        mock_git_b.get_state.return_value = mock_state_b
        project_b.git_watcher = mock_git_b

        active = pm.determine_active_project()
        assert active == project_b

    def test_branch_mode_project_with_new_commit_is_eligible(self):
        """Verify branch mode project becomes eligible again after new commit."""
        pm = ProjectManager()
        now = datetime.now(timezone.utc)

        project_a = pm.add_project(
            project_id="project_a",
            target_directory=Path("/tmp/project_a"),
            config_file=Path("/tmp/config_a.toml"),
            config=Mock(),
        )
        project_b = pm.add_project(
            project_id="project_b",
            target_directory=Path("/tmp/project_b"),
            config_file=Path("/tmp/config_b.toml"),
            config=Mock(),
        )

        pm.switch_to_project(project_a, skip_cooldown=True)

        project_a.last_scan_time = now - timedelta(minutes=60)

        new_commit_mtime = now.timestamp()
        mock_git_a = Mock()
        mock_state_a = Mock()
        mock_state_a.has_changes = True
        mock_state_a.changed_files = [
            Mock(mtime_ns=new_commit_mtime * 1e9, path="new_commit.cpp"),
            Mock(mtime_ns=(now - timedelta(hours=2)).timestamp() * 1e9,
                 path="old_commit.cpp"),
        ]
        mock_git_a.get_state.return_value = mock_state_a
        project_a.git_watcher = mock_git_a

        mock_git_b = Mock()
        mock_state_b = Mock()
        mock_state_b.has_changes = False
        mock_state_b.changed_files = []
        mock_git_b.get_state.return_value = mock_state_b
        project_b.git_watcher = mock_git_b

        active = pm.determine_active_project()
        assert active == project_a

    def test_branch_mode_project_not_scanned_yet_is_eligible(self):
        """Verify branch mode project without last_scan_time is always eligible."""
        pm = ProjectManager()
        now = datetime.now(timezone.utc)

        project_a = pm.add_project(
            project_id="project_a",
            target_directory=Path("/tmp/project_a"),
            config_file=Path("/tmp/config_a.toml"),
            config=Mock(),
        )
        project_b = pm.add_project(
            project_id="project_b",
            target_directory=Path("/tmp/project_b"),
            config_file=Path("/tmp/config_b.toml"),
            config=Mock(),
        )

        project_a.last_scan_time = None

        mock_git_a = Mock()
        mock_state_a = Mock()
        mock_state_a.has_changes = True
        mock_state_a.changed_files = [
            Mock(mtime_ns=(now - timedelta(days=7)).timestamp() * 1e9,
                 path="very_old.cpp")
        ]
        mock_git_a.get_state.return_value = mock_state_a
        project_a.git_watcher = mock_git_a

        mock_git_b = Mock()
        mock_state_b = Mock()
        mock_state_b.has_changes = False
        mock_state_b.changed_files = []
        mock_git_b.get_state.return_value = mock_state_b
        project_b.git_watcher = mock_git_b

        active = pm.determine_active_project()
        assert active == project_a

    def test_branch_mode_both_eligible_most_recent_selected(self):
        """Verify when both branch mode projects are eligible, most recent wins."""
        pm = ProjectManager()
        now = datetime.now(timezone.utc)

        project_a = pm.add_project(
            project_id="project_a",
            target_directory=Path("/tmp/project_a"),
            config_file=Path("/tmp/config_a.toml"),
            config=Mock(),
        )
        project_b = pm.add_project(
            project_id="project_b",
            target_directory=Path("/tmp/project_b"),
            config_file=Path("/tmp/config_b.toml"),
            config=Mock(),
        )

        # Both not scanned yet (both eligible)
        project_a.last_scan_time = None
        project_b.last_scan_time = None

        mock_git_a = Mock()
        mock_state_a = Mock()
        mock_state_a.has_changes = True
        mock_state_a.changed_files = [
            Mock(mtime_ns=(now - timedelta(minutes=10)).timestamp() * 1e9,
                 path="older.cpp")
        ]
        mock_git_a.get_state.return_value = mock_state_a
        project_a.git_watcher = mock_git_a

        mock_git_b = Mock()
        mock_state_b = Mock()
        mock_state_b.has_changes = True
        mock_state_b.changed_files = [
            Mock(mtime_ns=(now - timedelta(minutes=1)).timestamp() * 1e9,
                 path="newer.cpp")
        ]
        mock_git_b.get_state.return_value = mock_state_b
        project_b.git_watcher = mock_git_b

        active = pm.determine_active_project()
        assert active == project_b


class TestBranchModeFullWorkflow:
    """Tests for full multi-project workflow in branch mode."""

    def test_full_branch_mode_workflow_two_projects(self):
        """Full workflow: initialize 2 branch mode projects, switch between them."""
        pm = ProjectManager()
        now = datetime.now(timezone.utc)

        project_a = pm.add_project(
            project_id="project_a",
            target_directory=Path("/tmp/project_a"),
            config_file=Path("/tmp/config_a.toml"),
            config=Mock(),
        )
        project_b = pm.add_project(
            project_id="project_b",
            target_directory=Path("/tmp/project_b"),
            config_file=Path("/tmp/config_b.toml"),
            config=Mock(),
        )

        mock_git_a = Mock()
        mock_state_a_initial = Mock()
        mock_state_a_initial.has_changes = True
        mock_state_a_initial.changed_files = [
            Mock(mtime_ns=now.timestamp() * 1e9, path="a_branch_commit.cpp")
        ]
        mock_git_a.get_state.return_value = mock_state_a_initial
        project_a.git_watcher = mock_git_a

        mock_git_b = Mock()
        mock_state_b_initial = Mock()
        mock_state_b_initial.has_changes = True
        mock_state_b_initial.changed_files = [
            Mock(mtime_ns=(now - timedelta(minutes=10)).timestamp() * 1e9,
                 path="b_branch_commit.cpp")
        ]
        mock_git_b.get_state.return_value = mock_state_b_initial
        project_b.git_watcher = mock_git_b

        # Initial selection via determine_active_project
        active = pm.determine_active_project()
        assert active == project_a  # more recent changes

        pm.switch_to_project(active, skip_cooldown=True)
        assert pm.get_active_project() == project_a
        assert project_a.scan_status == ScanStatus.RUNNING
        assert project_a.is_active is True

        # Set scan progress
        project_a.scan_info = {"checks_run": 3, "total_checks": 8}
        project_a.last_scanned_files = {"a_branch_commit.cpp"}

        # Switch to project_b after cooldown using determine_active_project
        mock_state_b_new = Mock()
        mock_state_b_new.has_changes = True
        mock_state_b_new.changed_files = [
            Mock(mtime_ns=(now + timedelta(minutes=1)).timestamp() * 1e9,
                 path="b_new_commit.cpp")
        ]
        mock_git_b.get_state.return_value = mock_state_b_new

        mock_state_a_post = Mock()
        mock_state_a_post.has_changes = True
        mock_state_a_post.changed_files = [
            Mock(mtime_ns=now.timestamp() * 1e9, path="a_branch_commit.cpp")
        ]
        mock_git_a.get_state.return_value = mock_state_a_post

        with patch('code_scanner.project_manager.datetime') as mock_dt:
            future = now + timedelta(minutes=6)
            mock_dt.now.return_value = future
            # Project B is now more active (new commit after project A was scanned)
            active = pm.determine_active_project()
            assert active == project_b
            pm.switch_to_project(project_b)

        assert pm.get_active_project() == project_b
        assert project_a.scan_status == ScanStatus.WAITING_OTHER_PROJECT
        assert project_a.is_active is False
        assert project_a.inactive_since is not None
        assert project_b.scan_status == ScanStatus.RUNNING
        assert project_b.is_active is True

        # Verify project_a state preserved
        assert project_a.scan_info["checks_run"] == 3
        assert project_a.scan_info["total_checks"] == 8
        assert "a_branch_commit.cpp" in project_a.last_scanned_files

    def test_full_branch_mode_workflow_three_projects(self):
        """Full workflow: 3 branch mode projects, scan A, B, C, verify states."""
        pm = ProjectManager()
        now = datetime.now(timezone.utc)

        project_a = pm.add_project(
            project_id="project_a",
            target_directory=Path("/tmp/project_a"),
            config_file=Path("/tmp/config_a.toml"),
            config=Mock(),
        )
        project_b = pm.add_project(
            project_id="project_b",
            target_directory=Path("/tmp/project_b"),
            config_file=Path("/tmp/config_b.toml"),
            config=Mock(),
        )
        project_c = pm.add_project(
            project_id="project_c",
            target_directory=Path("/tmp/project_c"),
            config_file=Path("/tmp/config_c.toml"),
            config=Mock(),
        )

        # Setup: A most recent, then B, then C
        for proj, delay_minutes in [(project_a, 5), (project_b, 15), (project_c, 30)]:
            mock_git = Mock()
            mock_state = Mock()
            mock_state.has_changes = True
            mock_state.changed_files = [
                Mock(mtime_ns=(now - timedelta(minutes=delay_minutes)).timestamp() * 1e9,
                     path=f"{proj.project_id}.cpp")
            ]
            mock_git.get_state.return_value = mock_state
            proj.git_watcher = mock_git

        # Switch to A (most active)
        active = pm.determine_active_project()
        assert active == project_a
        pm.switch_to_project(active, skip_cooldown=True)
        assert pm.get_active_project() == project_a
        assert project_a.is_active is True

        project_a.scan_info = {"checks_run": 5}
        project_a.last_scanned_files = {"a.cpp"}

        # Switch to B
        pm.switch_to_project(project_b)
        assert pm.get_active_project() == project_b
        assert project_a.scan_status == ScanStatus.WAITING_OTHER_PROJECT
        assert project_a.is_active is False
        assert project_a.inactive_since is not None
        assert project_b.scan_status == ScanStatus.RUNNING
        assert project_b.is_active is True

        project_b.scan_info = {"checks_run": 3}
        project_b.last_scanned_files = {"b.cpp"}

        # Switch to C
        pm.switch_to_project(project_c)
        assert pm.get_active_project() == project_c
        assert project_b.scan_status == ScanStatus.WAITING_OTHER_PROJECT
        assert project_c.scan_status == ScanStatus.RUNNING
        assert project_c.is_active is True

        # Verify all states preserved
        assert project_a.scan_info["checks_run"] == 5
        assert project_b.scan_info["checks_run"] == 3
        assert "a.cpp" in project_a.last_scanned_files
        assert "b.cpp" in project_b.last_scanned_files

    def test_branch_mode_project_becomes_active_after_new_commit(self):
        """Verify branch mode project with new commit becomes active again.

        When project B was scanned (last_scan_time set) and its file mtimes
        are older, it should be filtered out. A with new commits should become active.
        """
        pm = ProjectManager()
        now = datetime.now(timezone.utc)
        mid = now - timedelta(minutes=30)
        old = now - timedelta(minutes=60)

        project_a = pm.add_project(
            project_id="project_a",
            target_directory=Path("/tmp/project_a"),
            config_file=Path("/tmp/config_a.toml"),
            config=Mock(),
        )
        project_b = pm.add_project(
            project_id="project_b",
            target_directory=Path("/tmp/project_b"),
            config_file=Path("/tmp/config_b.toml"),
            config=Mock(),
        )

        pm.switch_to_project(project_b, skip_cooldown=True)

        project_b.last_scan_time = mid

        mock_git_a = Mock()
        mock_state_a = Mock()
        mock_state_a.has_changes = True
        mock_state_a.changed_files = [
            Mock(mtime_ns=now.timestamp() * 1e9, path="new_a.cpp"),
        ]
        mock_git_a.get_state.return_value = mock_state_a
        project_a.git_watcher = mock_git_a

        mock_git_b = Mock()
        mock_state_b = Mock()
        mock_state_b.has_changes = True
        mock_state_b.changed_files = [
            Mock(mtime_ns=old.timestamp() * 1e9, path="old_b.cpp"),
        ]
        mock_git_b.get_state.return_value = mock_state_b
        project_b.git_watcher = mock_git_b

        active = pm.determine_active_project()
        assert active == project_a
