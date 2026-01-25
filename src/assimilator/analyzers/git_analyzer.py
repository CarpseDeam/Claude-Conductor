"""Analyzer for git repository context."""

import subprocess
from pathlib import Path
from typing import Any

from .base import BaseAnalyzer


class GitAnalyzer(BaseAnalyzer):
    """Analyzes git repository for context."""

    def can_analyze(self) -> bool:
        """Check if this is a git repository."""
        return (self.project_path / ".git").exists()

    def analyze(self) -> dict[str, Any]:
        """Analyze git repository."""
        return {
            "git_info": {
                "branch": self._get_current_branch(),
                "recent_files": self._get_hot_files(),
                "contributors": self._get_contributors(),
            }
        }

    def _run_git(self, args: list[str]) -> str | None:
        """Run git command and return output."""
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception as e:
            self.logger.debug("Git command failed: %s", e)
        return None

    def _get_current_branch(self) -> str:
        """Get current branch name."""
        output = self._run_git(["rev-parse", "--abbrev-ref", "HEAD"])
        return output or "unknown"

    def _get_hot_files(self, limit: int = 10) -> list[str]:
        """Get recently modified files from git history."""
        output = self._run_git([
            "log",
            "--pretty=format:",
            "--name-only",
            "-n", "50",
        ])
        if not output:
            return []

        file_counts: dict[str, int] = {}
        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue
            file_counts[line] = file_counts.get(line, 0) + 1

        sorted_files = sorted(file_counts.items(), key=lambda x: x[1], reverse=True)
        return [f for f, _ in sorted_files[:limit]]

    def _get_contributors(self, limit: int = 5) -> list[str]:
        """Get top contributors."""
        output = self._run_git([
            "shortlog",
            "-sn",
            "--no-merges",
            "-n", str(limit),
        ])
        if not output:
            return []

        contributors: list[str] = []
        for line in output.splitlines()[:limit]:
            parts = line.strip().split("\t", 1)
            if len(parts) == 2:
                contributors.append(parts[1])

        return contributors
