"""Analyzer for directory and file structure."""

from pathlib import Path
from typing import Any
import fnmatch

from .base import BaseAnalyzer


class StructureAnalyzer(BaseAnalyzer):
    """Analyzes directory structure and maps purposes."""

    DIRECTORY_PURPOSES: dict[str, str] = {
        "src": "Source code",
        "lib": "Library code",
        "app": "Application code",
        "tests": "Tests",
        "test": "Tests",
        "spec": "Tests",
        "docs": "Documentation",
        "doc": "Documentation",
        "config": "Configuration",
        "configs": "Configuration",
        "scripts": "Scripts",
        "bin": "Executables",
        "tools": "Tools",
        "utils": "Utilities",
        "helpers": "Helpers",
        "models": "Data models",
        "views": "Views",
        "controllers": "Controllers",
        "routes": "Route handlers",
        "api": "API endpoints",
        "services": "Business logic",
        "components": "UI components",
        "pages": "Page components",
        "static": "Static assets",
        "assets": "Assets",
        "public": "Public assets",
        "templates": "Templates",
        "migrations": "Database migrations",
        "fixtures": "Test fixtures",
        "mocks": "Test mocks",
    }

    FILE_EXTENSIONS: dict[str, str] = {
        ".py": "Python",
        ".js": "JavaScript",
        ".ts": "TypeScript",
        ".tsx": "TypeScript React",
        ".jsx": "JavaScript React",
        ".gd": "GDScript",
        ".java": "Java",
        ".go": "Go",
        ".rs": "Rust",
        ".rb": "Ruby",
        ".php": "PHP",
        ".cs": "C#",
        ".cpp": "C++",
        ".c": "C",
        ".h": "C/C++ Header",
        ".hpp": "C++ Header",
        ".swift": "Swift",
        ".kt": "Kotlin",
        ".scala": "Scala",
        ".vue": "Vue",
        ".svelte": "Svelte",
    }

    def can_analyze(self) -> bool:
        """Structure analyzer can always run."""
        return self.project_path.is_dir()

    def analyze(self) -> dict[str, Any]:
        """Analyze project structure."""
        gitignore_patterns = self._load_gitignore()
        structure = self._map_structure(gitignore_patterns)
        stats = self._compute_stats(gitignore_patterns)

        return {
            "structure": structure,
            "stats": stats,
        }

    def _load_gitignore(self) -> list[str]:
        """Load .gitignore patterns."""
        gitignore_path = self.project_path / ".gitignore"
        if not gitignore_path.exists():
            return self._default_ignore_patterns()

        patterns: list[str] = self._default_ignore_patterns()
        try:
            content = gitignore_path.read_text(encoding="utf-8")
            for line in content.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    patterns.append(line)
        except Exception as e:
            self.logger.debug("Failed to read .gitignore: %s", e)

        return patterns

    def _default_ignore_patterns(self) -> list[str]:
        """Return default patterns to ignore."""
        return [
            ".git",
            "__pycache__",
            "*.pyc",
            "node_modules",
            ".venv",
            "venv",
            ".env",
            "*.egg-info",
            "dist",
            "build",
            ".pytest_cache",
            ".mypy_cache",
            ".tox",
            "*.log",
            ".DS_Store",
            "Thumbs.db",
            ".conductor",
        ]

    def _is_ignored(self, path: Path, patterns: list[str]) -> bool:
        """Check if path matches any ignore pattern."""
        rel_path = str(path.relative_to(self.project_path))
        name = path.name

        for pattern in patterns:
            if fnmatch.fnmatch(name, pattern):
                return True
            if fnmatch.fnmatch(rel_path, pattern):
                return True
            if pattern.endswith("/") and fnmatch.fnmatch(name, pattern.rstrip("/")):
                return True

        return False

    def _map_structure(self, ignore_patterns: list[str]) -> dict[str, str]:
        """Map directory structure to purposes."""
        structure: dict[str, str] = {}

        for item in self.project_path.iterdir():
            if not item.is_dir():
                continue
            if self._is_ignored(item, ignore_patterns):
                continue

            name = item.name.lower()
            purpose = self.DIRECTORY_PURPOSES.get(name)

            if purpose:
                structure[f"{item.name}/"] = purpose
            else:
                sub_purpose = self._infer_purpose(item, ignore_patterns)
                if sub_purpose:
                    structure[f"{item.name}/"] = sub_purpose

        return structure

    def _infer_purpose(self, directory: Path, ignore_patterns: list[str]) -> str | None:
        """Infer directory purpose from contents."""
        try:
            files = list(directory.iterdir())[:50]
        except PermissionError:
            return None

        extensions: dict[str, int] = {}
        for f in files:
            if f.is_file() and not self._is_ignored(f, ignore_patterns):
                ext = f.suffix.lower()
                if ext in self.FILE_EXTENSIONS:
                    extensions[ext] = extensions.get(ext, 0) + 1

        if not extensions:
            return None

        dominant_ext = max(extensions, key=lambda x: extensions[x])
        lang = self.FILE_EXTENSIONS.get(dominant_ext, "")
        return f"{lang} files" if lang else None

    def _compute_stats(self, ignore_patterns: list[str]) -> dict[str, int]:
        """Compute file statistics."""
        stats: dict[str, int] = {"files": 0, "dirs": 0, "lines": 0}
        ext_counts: dict[str, int] = {}

        for path in self._walk_files(ignore_patterns):
            if path.is_file():
                stats["files"] += 1
                ext = path.suffix.lower()
                ext_counts[ext] = ext_counts.get(ext, 0) + 1

                if ext in self.FILE_EXTENSIONS:
                    try:
                        content = path.read_text(encoding="utf-8", errors="ignore")
                        stats["lines"] += len(content.splitlines())
                    except Exception:
                        pass
            elif path.is_dir():
                stats["dirs"] += 1

        return stats

    def _walk_files(self, ignore_patterns: list[str]) -> list[Path]:
        """Walk project files respecting ignore patterns."""
        result: list[Path] = []
        stack: list[Path] = [self.project_path]

        while stack:
            current = stack.pop()
            try:
                for item in current.iterdir():
                    if self._is_ignored(item, ignore_patterns):
                        continue
                    result.append(item)
                    if item.is_dir():
                        stack.append(item)
            except PermissionError:
                continue

        return result
