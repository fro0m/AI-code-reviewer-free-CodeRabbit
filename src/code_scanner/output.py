"""Markdown output generation."""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from .issue_tracker import IssueTracker
from .models import Issue, IssueStatus, ScanStatus

logger = logging.getLogger(__name__)


def _strip_code_fences(text: str) -> str:
    """Strip markdown code fences from text if present.

    Handles cases where LLM responses include their own code fences.
    Removes opening ``` (with optional language hint) and closing ```.

    Args:
        text: Text that may contain code fences.

    Returns:
        Text with code fences removed, preserving inner content.
    """
    if not text:
        return text

    # Pattern to match code blocks: ```[language]\n...\n```
    # This handles both ```python and just ```
    pattern = r'^```[a-zA-Z0-9]*\n?(.*?)\n?```$'
    match = re.match(pattern, text.strip(), re.DOTALL)
    if match:
        return match.group(1).strip()

    return text


def _contains_code_fences(text: str) -> bool:
    """Check if text contains markdown code fences.

    Args:
        text: Text to check.

    Returns:
        True if text contains ``` markers.
    """
    return '```' in text if text else False


class OutputGenerator:
    """Generates Markdown output file with scan results."""

    def __init__(self, output_path: Path):
        """Initialize output generator.

        Args:
            output_path: Path to output Markdown file.
        """
        self.output_path = output_path

    def write(self, tracker: IssueTracker, scan_info: Optional[dict] = None,
              scan_status: Optional[ScanStatus] = None, check_index: int = 0,
              total_checks: int = 0, check_query: str = "", error_message: str = "",
              inactive_since: Optional[datetime] = None, active_since: Optional[datetime] = None) -> None:
        """Write full output file.

        Rewrites entire file with current issue state.

        Args:
            tracker: Issue tracker with current issues.
            scan_info: Optional scan metadata (files scanned, etc.)
            scan_status: Optional scan status.
            check_index: Current check index (1-based) for RUNNING status.
            total_checks: Total number of checks for RUNNING status.
            check_query: Current check query for RUNNING status.
            error_message: Error message for ERROR or CONNECTION_LOST status.
            inactive_since: Optional timestamp for WAITING_OTHER_PROJECT status.
            active_since: Optional timestamp for RUNNING status.
        """
        content = self._generate_content(tracker, scan_info, scan_status,
                                       check_index, total_checks, check_query, error_message,
                                       inactive_since, active_since)

        try:
            with open(self.output_path, "w", encoding="utf-8") as f:
                f.write(content)
            logger.debug(f"Wrote output to {self.output_path}")
        except IOError as e:
            logger.error(f"Failed to write output file: {e}")
            raise

    def _generate_content(
        self,
        tracker: IssueTracker,
        scan_info: Optional[dict] = None,
        scan_status: Optional[ScanStatus] = None,
        check_index: int = 0,
        total_checks: int = 0,
        check_query: str = "",
        error_message: str = "",
        inactive_since: Optional[datetime] = None,
        active_since: Optional[datetime] = None,
    ) -> str:
        """Generate Markdown content.

        Args:
            tracker: Issue tracker with current issues.
            scan_info: Optional scan metadata.
            scan_status: Optional scan status.
            check_index: Current check index (1-based) for RUNNING status.
            total_checks: Total number of checks for RUNNING status.
            check_query: Current check query for RUNNING status.
            error_message: Error message for ERROR or CONNECTION_LOST status.
            inactive_since: Optional timestamp for WAITING_OTHER_PROJECT status.
            active_since: Optional timestamp for RUNNING status.

        Returns:
            Complete Markdown content.
        """
        lines: list[str] = []

        # Header
        lines.append("# Code Scanner Results")
        lines.append("")
        # Format: "January 25, 2026 at 9:05 PM" (local time, no timezone)
        lines.append(f"*Last updated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}*")
        lines.append("")

        # Summary
        stats = tracker.get_stats()
        lines.append("## Summary")
        lines.append("")

        # Status section
        if scan_status:
            status_text = scan_status.get_display_text(check_index, total_checks, check_query, error_message,
                                                     inactive_since=inactive_since, active_since=active_since)
            lines.append(f"- **Status:** {status_text}")
            lines.append("")

        lines.append(f"- **Open Issues:** {stats['open']}")
        lines.append(f"- **Resolved Issues:** {stats['resolved']}")
        lines.append(f"- **Total Issues:** {stats['total']}")
        lines.append("")

        # Scan info
        if scan_info:
            lines.append("## Scan Information")
            lines.append("")
            if "files_scanned" in scan_info:
                lines.append(f"- **Files Scanned:** {len(scan_info['files_scanned'])}")
            if "skipped_files" in scan_info:
                lines.append(f"- **Files Skipped:** {len(scan_info['skipped_files'])}")
            if "checks_run" in scan_info:
                checks_run = scan_info['checks_run']
                total_checks = scan_info.get('total_checks', checks_run)
                lines.append(f"- **Checks Run:** {checks_run}/{total_checks}")
            lines.append("")

        # Issues by file
        issues_by_file = tracker.get_issues_by_file()

        if not issues_by_file:
            lines.append("## Issues")
            lines.append("")
            lines.append("*No issues detected.*")
            lines.append("")
        else:
            lines.append("## Issues by File")
            lines.append("")

            for file_path, issues in issues_by_file.items():
                lines.append(f"### `{file_path}`")
                lines.append("")

                for issue in issues:
                    lines.extend(self._format_issue(issue))
                    lines.append("")

        # Footer
        lines.append("---")
        lines.append("")
        lines.append("*Generated by [Code Scanner](https://github.com/ubego/Code-Scanner)*")
        lines.append("")
        lines.append("⭐ **[Star Code Scanner on GitHub](https://github.com/ubego/Code-Scanner)** if you find it useful!")

        return "\n".join(lines)

    def _format_issue(self, issue: Issue) -> list[str]:
        """Format a single issue as Markdown.

        Args:
            issue: The issue to format.

        Returns:
            List of Markdown lines.
        """
        lines: list[str] = []

        # Status badge
        status_badge = "🔴 OPEN" if issue.status == IssueStatus.OPEN else "✅ RESOLVED"

        lines.append(f"#### Line {issue.line_number} - {status_badge}")
        lines.append("")

        # Metadata - use local time
        lines.append(f"**Detected:** {issue.timestamp.strftime('%B %d, %Y at %I:%M %p')}")
        lines.append("")
        lines.append(f"**Check:** {issue.check_query}")
        lines.append("")

        # Description
        lines.append("**Issue:**")
        lines.append("")
        lines.append(issue.description)
        lines.append("")

        # Code snippet if available
        if issue.code_snippet:
            lines.append("**Problematic Code:**")
            lines.append("")
            # Only wrap in code fences if content doesn't already contain them
            if _contains_code_fences(issue.code_snippet):
                lines.append(issue.code_snippet)
            else:
                lines.append("```")
                lines.append(issue.code_snippet)
                lines.append("```")
            lines.append("")

        # Suggested fix
        if issue.suggested_fix:
            lines.append("**Suggested Fix:**")
            lines.append("")
            # Only wrap in code fences if content doesn't already contain them
            if _contains_code_fences(issue.suggested_fix):
                lines.append(issue.suggested_fix)
            else:
                lines.append("```")
                lines.append(issue.suggested_fix)
                lines.append("```")
            lines.append("")

        return lines
