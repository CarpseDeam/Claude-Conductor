"""Git information extraction for codebase mapping."""
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class RecentCommit:
    """Info about a recent commit."""
    hash: str
    message: str
    files: list[str]


class GitInfoExtractor:
    """Extracts git information for codebase context."""

    def get_recent_commits(self, project_path: Path, limit: int = 5) -> list[RecentCommit]:
        """Get recent commits with files changed."""
        try:
            result = subprocess.run(
                ["git", "log", f"-{limit}", "--pretty=format:%h|%s"],
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                return []

            commits = []
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue
                hash_val, message = line.split('|', 1)
                files = self._get_commit_files(project_path, hash_val)
                commits.append(RecentCommit(hash_val, message, files))

            return commits
        except Exception:
            return []

    def _get_commit_files(self, project_path: Path, commit_hash: str) -> list[str]:
        """Get files changed in a commit."""
        try:
            result = subprocess.run(
                ["git", "show", "--name-only", "--pretty=format:", commit_hash],
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                return []
            return [f for f in result.stdout.strip().split('\n') if f]
        except Exception:
            return []

    def get_uncommitted_changes(self, project_path: Path) -> list[str]:
        """Get list of uncommitted changed files."""
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                return []

            files = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    files.append(line[3:])
            return files
        except Exception:
            return []
