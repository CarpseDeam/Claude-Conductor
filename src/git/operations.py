import os
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
            encoding='utf-8',
            errors='replace',
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

    def has_remote(self, project_path: Path) -> bool:
        """Check if the git repo has any remotes configured."""
        result = self._run(["git", "remote"], project_path)
        return result.returncode == 0 and bool(result.stdout.strip())

    @staticmethod
    def is_claude_branch(branch: str) -> bool:
        return branch.startswith("claude/")

    def cleanup_windows_artifacts(self, project_path: Path) -> None:
        """Delete Windows reserved name files that break git."""
        reserved_names = ["nul", "con", "aux", "prn", "com1", "com2", "com3", "com4", "lpt1", "lpt2", "lpt3"]
        for name in reserved_names:
            file_path = project_path / name
            if file_path.exists():
                try:
                    os.remove(f"\\\\?\\{file_path.resolve()}")
                except Exception:
                    pass

    def ensure_gitignore(self, project_path: Path) -> bool:
        """Create a sensible .gitignore if one doesn't exist. Returns True if created."""
        gitignore_path = project_path / ".gitignore"
        if gitignore_path.exists():
            return False

        content = self._generate_gitignore(project_path)
        gitignore_path.write_text(content, encoding='utf-8')
        return True

    def _generate_gitignore(self, project_path: Path) -> str:
        """Generate .gitignore content based on detected project type."""
        lines = [
            "# === Universal ===",
            ".DS_Store",
            "Thumbs.db",
            "*.log",
            ".env",
            ".env.local",
            "",
            "# === Windows artifacts (reserved names) ===",
            "nul",
            "con",
            "aux",
            "prn",
            "",
            "# === IDE ===",
            ".idea/",
            ".vscode/",
            "*.swp",
            "*.swo",
            "",
        ]

        if (project_path / "project.godot").exists():
            lines.extend([
                "# === Godot ===",
                ".godot/",
                "*.import",
                "export_presets.cfg",
                "",
            ])

        if (project_path / "requirements.txt").exists() or (project_path / "pyproject.toml").exists() or list(project_path.glob("*.py")):
            lines.extend([
                "# === Python ===",
                "__pycache__/",
                "*.py[cod]",
                "*$py.class",
                ".venv/",
                "venv/",
                "*.egg-info/",
                "dist/",
                "build/",
                ".pytest_cache/",
                ".mypy_cache/",
                "",
            ])

        if (project_path / "package.json").exists():
            lines.extend([
                "# === Node.js ===",
                "node_modules/",
                "npm-debug.log",
                "yarn-error.log",
                ".npm/",
                "",
            ])

        if (project_path / "Cargo.toml").exists():
            lines.extend([
                "# === Rust ===",
                "target/",
                "Cargo.lock",
                "",
            ])

        return "\n".join(lines)
