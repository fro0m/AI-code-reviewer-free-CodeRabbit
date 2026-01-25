"""Data models for the code scanner."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

from .text_utils import normalize_whitespace as _normalize_whitespace
from .text_utils import similarity_ratio as _similarity_ratio


class IssueStatus(Enum):
    """Status of a detected issue."""

    OPEN = "OPEN"
    RESOLVED = "RESOLVED"


class FileStatus(Enum):
    """Status of a file with uncommitted changes."""

    STAGED = "staged"
    UNSTAGED = "unstaged"
    UNTRACKED = "untracked"
    DELETED = "deleted"


class ScanStatus(Enum):
    """Status of the scan for a project."""

    INITIALIZING = "initializing"
    RUNNING = "running"
    WAITING_OTHER_PROJECT = "waiting_other_project"
    WAITING_NO_CHANGES = "waiting_no_changes"
    WAITING_MERGE_REBASE = "waiting_merge_rebase"
    NOT_RUNNING = "not_running"
    ERROR = "error"
    CONNECTION_LOST = "connection_lost"

    def get_display_text(self, check_index: int = 0, total_checks: int = 0, 
                         check_query: str = "", error_message: str = "") -> str:
        """Get the display text for this status.

        Args:
            check_index: Current check index (1-based) for RUNNING status.
            total_checks: Total number of checks for RUNNING status.
            check_query: Current check query for RUNNING status.
            error_message: Error message for ERROR or CONNECTION_LOST status.

        Returns:
            Formatted display text with icon and details.
        """
        icon = self.get_icon()
        
        if self == ScanStatus.RUNNING:
            if check_query:
                return f"{icon} Running - Check {check_index}/{total_checks}: {check_query}"
            return f"{icon} Running - Check {check_index}/{total_checks}"
        elif self == ScanStatus.WAITING_OTHER_PROJECT:
            return f"{icon} Waiting - Another project is currently being scanned"
        elif self == ScanStatus.WAITING_NO_CHANGES:
            return f"{icon} Waiting - No uncommitted changes detected"
        elif self == ScanStatus.WAITING_MERGE_REBASE:
            return f"{icon} Waiting - Merge/rebase conflict resolution in progress"
        elif self == ScanStatus.NOT_RUNNING:
            return f"{icon} Not running"
        elif self == ScanStatus.ERROR:
            return f"{icon} Error - {error_message}"
        elif self == ScanStatus.CONNECTION_LOST:
            return f"{icon} Connection lost - Waiting for LLM server"
        elif self == ScanStatus.INITIALIZING:
            return f"{icon} Initializing"
        else:
            return f"{icon} {self.value}"

    def get_icon(self) -> str:
        """Get the icon for this status.

        Returns:
            Unicode icon character.
        """
        icons = {
            ScanStatus.INITIALIZING: "🔧",
            ScanStatus.RUNNING: "🔄",
            ScanStatus.WAITING_OTHER_PROJECT: "⏳",
            ScanStatus.WAITING_NO_CHANGES: "⏳",
            ScanStatus.WAITING_MERGE_REBASE: "⏳",
            ScanStatus.NOT_RUNNING: "⏹️",
            ScanStatus.ERROR: "❌",
            ScanStatus.CONNECTION_LOST: "🔌",
        }
        return icons.get(self, "")


@dataclass
class Issue:
    """Represents a single issue detected by the scanner."""

    file_path: str
    line_number: int
    description: str
    suggested_fix: str
    check_query: str
    timestamp: datetime
    status: IssueStatus = IssueStatus.OPEN
    code_snippet: str = ""

    def matches(self, other: "Issue", fuzzy_threshold: float = 0.8) -> bool:
        """Check if this issue matches another issue for deduplication.

        Issues match if they have the same file and similar code pattern/description.
        Line numbers are NOT used for matching as code can move.
        
        Uses fuzzy matching with Levenshtein distance for more robust comparison
        that handles minor code changes.

        Args:
            other: The other issue to compare against.
            fuzzy_threshold: Minimum similarity ratio (0.0 to 1.0) to consider a match.
                           Default 0.8 (80% similarity).

        Returns:
            True if issues match (should be deduplicated).
        """
        if self.file_path != other.file_path:
            return False

        # Normalize whitespace for comparison
        self_snippet = _normalize_whitespace(self.code_snippet)
        other_snippet = _normalize_whitespace(other.code_snippet)

        self_desc = _normalize_whitespace(self.description)
        other_desc = _normalize_whitespace(other.description)

        # Exact match first (fast path)
        if self_snippet == other_snippet or self_desc == other_desc:
            return True

        # Fuzzy match for code snippets using similarity ratio
        if self_snippet and other_snippet:
            snippet_similarity = _similarity_ratio(self_snippet, other_snippet)
            if snippet_similarity >= fuzzy_threshold:
                return True

        # Fuzzy match for descriptions
        if self_desc and other_desc:
            desc_similarity = _similarity_ratio(self_desc, other_desc)
            if desc_similarity >= fuzzy_threshold:
                return True

        return False

    @classmethod
    def from_llm_response(
        cls,
        data: dict,
        check_query: str,
        timestamp: Optional[datetime] = None,
    ) -> "Issue":
        """Create an Issue from LLM response data."""
        # Handle None values from LLM - use 'or' to fall back when key exists but value is None
        line_num = data.get("line_number") or data.get("line") or 0
        return cls(
            file_path=data.get("file") or data.get("file_path") or "",
            line_number=int(line_num),
            description=data.get("description") or "",
            suggested_fix=data.get("suggested_fix") or data.get("fix") or "",
            check_query=check_query,
            timestamp=timestamp or datetime.now(timezone.utc),
            code_snippet=data.get("code_snippet") or "",
        )


@dataclass
class ChangedFile:
    """Represents a file with uncommitted changes."""

    path: str
    status: FileStatus | str  # 'staged', 'unstaged', 'untracked', 'deleted'
    mtime_ns: Optional[int] = None  # Nanosecond-precision mtime for change detection

    def __post_init__(self):
        """Convert string status to FileStatus enum for type safety."""
        if isinstance(self.status, str):
            # Map string values to enum values
            status_map = {
                "staged": FileStatus.STAGED,
                "unstaged": FileStatus.UNSTAGED,
                "untracked": FileStatus.UNTRACKED,
                "deleted": FileStatus.DELETED,
                "modified": FileStatus.UNSTAGED,  # Map 'modified' to 'unstaged' for backward compatibility
            }
            self.status = status_map.get(self.status, FileStatus.UNSTAGED)

    @property
    def is_deleted(self) -> bool:
        """Check if file is deleted."""
        return self.status == FileStatus.DELETED


@dataclass
class GitState:
    """Current state of Git repository."""

    changed_files: list[ChangedFile] = field(default_factory=list)
    is_merging: bool = False
    is_rebasing: bool = False

    @property
    def is_conflict_resolution_in_progress(self) -> bool:
        """Check if merge/rebase conflict resolution is in progress."""
        return self.is_merging or self.is_rebasing

    @property
    def has_changes(self) -> bool:
        """Check if there are any uncommitted changes."""
        return len(self.changed_files) > 0


@dataclass
class LLMConfig:
    """Configuration for LLM backend connection.
    
    Supports both LM Studio and Ollama backends.
    The 'backend' field is required and must be explicitly set.
    """

    backend: str  # Required: "lm-studio" or "ollama"
    host: str  # Required: no default
    port: int  # Required: no default
    model: Optional[str] = None  # Required for Ollama, optional for LM Studio
    timeout: int = 120
    context_limit: Optional[int] = None  # Manual override for context window size

    # Valid backend values
    VALID_BACKENDS = ("lm-studio", "ollama")

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        if self.backend not in self.VALID_BACKENDS:
            raise ValueError(
                f"Invalid backend '{self.backend}'. "
                f"Must be one of: {', '.join(self.VALID_BACKENDS)}"
            )
        
        if self.backend == "ollama" and not self.model:
            raise ValueError(
                "Ollama backend requires 'model' to be specified.\n"
                "Example: model = \"qwen3:4b\""
            )

    @property
    def base_url(self) -> str:
        """Get the base URL for LLM API."""
        if self.backend == "lm-studio":
            return f"http://{self.host}:{self.port}/v1"
        else:  # ollama
            return f"http://{self.host}:{self.port}"


@dataclass
class CheckGroup:
    """A group of checks that apply to files matching a pattern."""

    pattern: str  # Glob pattern like "*.cpp, *.h" or "*" for all files
    checks: list[str]  # List of checks to run

    def matches_file(self, file_path: str) -> bool:
        """Check if the file matches this check group's pattern.

        Supports:
        - File extension patterns: *.cpp, *.h
        - Wildcard: * matches all files
        - Directory patterns: /*dirname*/ matches files in directories containing 'dirname'

        Args:
            file_path: The file path to check.

        Returns:
            True if the file matches the pattern.
        """
        from fnmatch import fnmatch

        # Split patterns by comma and strip whitespace
        patterns = [p.strip() for p in self.pattern.split(",")]

        # Get just the filename for matching
        filename = file_path.split("/")[-1] if "/" in file_path else file_path

        # Check if any pattern matches
        for pattern in patterns:
            # Check for directory pattern: /*dirname*/
            if pattern.startswith("/") and pattern.endswith("/") and len(pattern) > 2:
                dir_pattern = pattern[1:-1]  # Remove leading and trailing /
                # Check if any directory component matches the pattern
                path_parts = file_path.replace("\\", "/").split("/")
                for part in path_parts[:-1]:  # Exclude the filename itself
                    if fnmatch(part, dir_pattern):
                        return True
            elif fnmatch(filename, pattern) or fnmatch(file_path, pattern):
                return True

        return False


@dataclass
class Project:
    """Represents a monitored project with all its components."""

    project_id: str  # Unique identifier (e.g., "project_1")
    target_directory: Path
    config_file: Path
    config: "Config"
    git_watcher: Optional["GitWatcher"] = None
    issue_tracker: Optional["IssueTracker"] = None
    ctags_index: Optional["CtagsIndex"] = None
    output_generator: Optional["OutputGenerator"] = None
    file_filter: Optional["FileFilter"] = None

    # State tracking
    last_activity_time: float = 0.0  # Unix timestamp
    is_active: bool = False
    last_scanned_files: set[str] = field(default_factory=set)
    last_file_contents_hash: dict[str, int] = field(default_factory=dict)
    scan_info: dict = field(default_factory=dict)  # Scan progress information (checks_run, total_checks, etc.)
    
    # Scan status tracking
    scan_status: ScanStatus = ScanStatus.INITIALIZING
    current_check_index: int = 0  # 1-based index of current check
    total_checks: int = 0  # Total number of checks in current scan
    current_check_query: str = ""  # Current check query being executed
    error_message: str = ""  # Error message for ERROR or CONNECTION_LOST status

    @property
    def output_path(self) -> Path:
        """Get output file path for this project."""
        return self.target_directory / self.config.output_file
