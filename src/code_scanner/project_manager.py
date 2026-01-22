"""Project manager for multi-project support."""

import threading
from pathlib import Path
from typing import Optional

from code_scanner.models import Project
from code_scanner.utils import logger


class ProjectManager:
    """Manages multiple projects and handles project switching."""

    def __init__(self):
        """Initialize the project manager."""
        self._projects: dict[str, Project] = {}
        self._active_project_id: Optional[str] = None
        self._previous_active_project_id: Optional[str] = None
        self._lock = threading.Lock()

    def add_project(
        self,
        project_id: str,
        target_directory: Path,
        config_file: Path,
        config: "Config",
    ) -> Project:
        """Add a new project to monitor.

        Args:
            project_id: Unique identifier for the project.
            target_directory: Path to the project directory.
            config_file: Path to the configuration file.
            config: Configuration object.

        Returns:
            The created Project object.
        """
        project = Project(
            project_id=project_id,
            target_directory=target_directory,
            config_file=config_file,
            config=config,
        )
        with self._lock:
            self._projects[project_id] = project
        return project

    def determine_active_project(self) -> Optional[Project]:
        """Determine which project should be active based on most recent changes.

        Uses existing git change detection algorithm from GitWatcher.
        The project with the highest max mtime_ns among changed files becomes active.

        Returns:
            The project that should be active, or None if no projects exist.
        """
        with self._lock:
            if not self._projects:
                return None

            if len(self._projects) == 1:
                return next(iter(self._projects.values()))

            # Get git state for all projects
            project_activity: dict[str, float] = {}
            for project_id, project in self._projects.items():
                if project.git_watcher is None:
                    continue

                state = project.git_watcher.get_state()
                if state.has_changes:
                    # Find max mtime among changed files
                    max_mtime = max(
                        (f.mtime_ns for f in state.changed_files if f.mtime_ns is not None),
                        default=0.0
                    )
                    project_activity[project_id] = max_mtime

            # Find project with highest activity
            if not project_activity:
                # No changes in any project, keep current active
                return self.get_active_project()

            most_active_id = max(project_activity, key=project_activity.get)
            return self._projects[most_active_id]

    def switch_to_project(self, project: Project) -> None:
        """Switch to a different project.

        This is non-blocking - waits for current check to complete.

        Args:
            project: The project to switch to.
        """
        with self._lock:
            if self._active_project_id == project.project_id:
                return  # Already active

            self._previous_active_project_id = self._active_project_id
            self._active_project_id = project.project_id

            # Update project states
            for p in self._projects.values():
                p.is_active = (p.project_id == project.project_id)

            logger.info(f"Switched to active project: {project.project_id} ({project.target_directory})")

    def get_active_project(self) -> Optional[Project]:
        """Get currently active project.

        Returns:
            The active project, or None if no project is active.
        """
        with self._lock:
            return self._projects.get(self._active_project_id) if self._active_project_id else None

    def get_previous_active_project(self) -> Optional[Project]:
        """Get previously active project.

        Returns:
            The previously active project, or None if there was no previous project.
        """
        with self._lock:
            return self._projects.get(self._previous_active_project_id) if self._previous_active_project_id else None

    def get_all_projects(self) -> list[Project]:
        """Get all projects.

        Returns:
            List of all projects.
        """
        with self._lock:
            return list(self._projects.values())

    def get_project_by_id(self, project_id: str) -> Optional[Project]:
        """Get a project by its ID.

        Args:
            project_id: The project ID.

        Returns:
            The project, or None if not found.
        """
        with self._lock:
            return self._projects.get(project_id)

    def get_project_by_directory(self, directory: Path) -> Optional[Project]:
        """Get a project by its target directory.

        Args:
            directory: The target directory path.

        Returns:
            The project, or None if not found.
        """
        with self._lock:
            for project in self._projects.values():
                if project.target_directory == directory:
                    return project
            return None
