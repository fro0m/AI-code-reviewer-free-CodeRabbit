"""Project manager for multi-project support."""

import threading
from pathlib import Path
from typing import Optional

from .models import Project, ScanStatus
from .utils import logger


class ProjectManager:
    """Manages multiple projects and handles project switching."""

    def __init__(self):
        """Initialize the project manager."""
        self._projects: dict[str, Project] = {}
        self._active_project_id: Optional[str] = None
        self._previous_active_project_id: Optional[str] = None
        self._lock = threading.RLock()

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
                logger.debug(f"Only one project, returning: {list(self._projects.keys())[0]}")
                return next(iter(self._projects.values()))

            # Get git state for all projects
            project_activity: dict[str, float] = {}
            for project_id, project in self._projects.items():
                if project.git_watcher is None:
                    logger.debug(f"Project {project_id} has no git watcher, skipping")
                    continue

                state = project.git_watcher.get_state()
                logger.debug(f"Project {project_id}: has_changes={state.has_changes}, changed_files={len(state.changed_files)}")
                if state.has_changes:
                    # Find max mtime among changed files
                    max_mtime = max(
                        (f.mtime_ns for f in state.changed_files if f.mtime_ns is not None),
                        default=0.0
                    )
                    project_activity[project_id] = max_mtime
                    logger.debug(f"Project {project_id}: max_mtime_ns={max_mtime}, changed_files_with_mtime={sum(1 for f in state.changed_files if f.mtime_ns is not None)}")
                else:
                    logger.debug(f"Project {project_id}: no changes detected")

            # Find project with highest activity
            if not project_activity:
                # No changes in any project, keep current active
                logger.debug("No projects with changes, keeping current active project")
                return self.get_active_project()

            most_active_id = max(project_activity, key=project_activity.get)
            logger.info(f"Project activity comparison: {project_activity}")
            logger.info(f"Selected most active project: {most_active_id} (max_mtime_ns={project_activity[most_active_id]})")
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

            previous_project = self.get_active_project()
            self._previous_active_project_id = self._active_project_id
            self._active_project_id = project.project_id

            # Update project states
            for p in self._projects.values():
                p.is_active = (p.project_id == project.project_id)

            logger.info(f"Switched to active project: {project.project_id} ({project.target_directory})")

            # Update status for previous project (if exists) to WAITING_OTHER_PROJECT
            if previous_project is not None:
                logger.info(f"Setting previous project {previous_project.project_id} to WAITING_OTHER_PROJECT")
                previous_project.scan_status = ScanStatus.WAITING_OTHER_PROJECT
                if previous_project.output_generator is not None:
                    logger.debug(f"Updating output file for previous project {previous_project.project_id}")
                    previous_project.output_generator.write(
                        previous_project.issue_tracker,
                        {},
                        previous_project.scan_status,
                        previous_project.current_check_index,
                        previous_project.total_checks,
                        previous_project.current_check_query,
                        previous_project.error_message,
                    )
                else:
                    logger.warning(f"Output generator is None for previous project {previous_project.project_id}")

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

    def set_all_projects_status(self, status: ScanStatus, error_message: str = "") -> None:
        """Set the scan status for all projects.

        Args:
            status: The scan status to set for all projects.
            error_message: Optional error message for ERROR or CONNECTION_LOST status.
        """
        with self._lock:
            for project in self._projects.values():
                logger.debug(f"Setting project {project.project_id} to status: {status.value}")
                project.scan_status = status
                project.error_message = error_message
                if project.output_generator is not None:
                    project.output_generator.write(
                        project.issue_tracker,
                        {},
                        project.scan_status,
                        project.current_check_index,
                        project.total_checks,
                        project.current_check_query,
                        project.error_message,
                    )
                else:
                    logger.warning(f"Output generator is None for project {project.project_id}")
        logger.info(f"Set all projects to status: {status.value}")
