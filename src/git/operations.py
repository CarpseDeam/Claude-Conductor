import subprocess
from pathlib import Path

from .contracts import GitDiff, CommitResult


class GitOperations:
    TIMEOUT = 30

    def _run(self, args: list[str], cwd: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=self.TIMEOUT,
        )

    def get_diff(self, project_path: Path) -> GitDiff:
        diff_result = self._run(["git", "diff", "HEAD"], project_path)
        files_result = self._run(
            ["git", "diff", "HEAD", "--name-only"], project_path
        )

        content = diff_result.stdout
        files_changed = [
            f for f in files_result.stdout.strip().split("\n") if f
        ]
        has_changes = bool(content.strip())

        return GitDiff(
            content=content,
            files_changed=files_changed,
            has_changes=has_changes,
        )

    def stage_all(self, project_path: Path) -> bool:
        result = self._run(["git", "add", "-A"], project_path)
        return result.returncode == 0

    def commit(self, project_path: Path, message: str) -> CommitResult:
        result = self._run(["git", "commit", "-m", message], project_path)

        if result.returncode != 0:
            return CommitResult(
                success=False,
                hash=None,
                message=message,
                error=result.stderr.strip(),
            )

        hash_result = self._run(
            ["git", "rev-parse", "--short", "HEAD"], project_path
        )
        commit_hash = hash_result.stdout.strip() if hash_result.returncode == 0 else None

        return CommitResult(
            success=True,
            hash=commit_hash,
            message=message,
        )

    def push(self, project_path: Path, branch: str | None = None) -> bool:
        if branch:
            result = self._run(
                ["git", "push", "-u", "origin", branch], project_path
            )
        else:
            result = self._run(["git", "push"], project_path)

        if result.returncode != 0 and "no upstream branch" in result.stderr:
            current = self.get_current_branch(project_path)
            if current:
                result = self._run(
                    ["git", "push", "-u", "origin", current], project_path
                )

        return result.returncode == 0

    def get_current_branch(self, project_path: Path) -> str | None:
        result = self._run(["git", "branch", "--show-current"], project_path)
        if result.returncode == 0:
            return result.stdout.strip() or None
        return None

    def checkout(self, project_path: Path, branch: str) -> bool:
        result = self._run(["git", "checkout", branch], project_path)
        return result.returncode == 0

    def merge(self, project_path: Path, source_branch: str) -> bool:
        result = self._run(["git", "merge", source_branch], project_path)
        return result.returncode == 0

    def delete_branch(self, project_path: Path, branch: str) -> bool:
        result = self._run(["git", "branch", "-d", branch], project_path)
        return result.returncode == 0

    @staticmethod
    def is_claude_branch(branch: str) -> bool:
        return branch.startswith("claude/")
