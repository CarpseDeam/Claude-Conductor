"""Extractor for detecting coding patterns and conventions."""

import ast
import re
from pathlib import Path
from typing import Any

from .base import BaseExtractor
from ..manifest import Pattern


class PatternsExtractor(BaseExtractor):
    """Detects coding patterns and conventions in the codebase."""

    def can_extract(self) -> bool:
        """Check if project has Python files."""
        return any(self.project_path.rglob("*.py"))

    def extract(self) -> dict[str, Any]:
        """Extract patterns from the codebase."""
        patterns: list[Pattern] = []

        patterns.extend(self._detect_error_patterns())
        patterns.extend(self._detect_auth_patterns())
        patterns.extend(self._detect_di_patterns())
        patterns.extend(self._detect_test_patterns())
        patterns.extend(self._detect_async_patterns())
        patterns.extend(self._detect_orm_patterns())

        return {"patterns": patterns}

    def _get_python_files(self, limit: int = 50) -> list[Path]:
        """Get Python files, excluding common non-source directories."""
        files: list[Path] = []
        for py_file in self.project_path.rglob("*.py"):
            if self._should_skip(py_file):
                continue
            files.append(py_file)
            if len(files) >= limit:
                break
        return files

    def _should_skip(self, path: Path) -> bool:
        """Check if path should be skipped."""
        skip_dirs = {"__pycache__", ".venv", "venv", "node_modules", ".git", "dist", "build"}
        return any(part in skip_dirs for part in path.parts)

    def _detect_error_patterns(self) -> list[Pattern]:
        """Detect error handling patterns."""
        patterns: list[Pattern] = []
        files = self._get_python_files()

        for py_file in files:
            try:
                content = py_file.read_text(encoding="utf-8")
            except Exception:
                continue

            if "HTTPException" in content:
                if "detail=" in content:
                    patterns.append(Pattern(
                        name="errors",
                        description="HTTPException with detail dict",
                        examples=[str(py_file.relative_to(self.project_path))],
                    ))
                    break

            if re.search(r"raise\s+\w+Error", content):
                patterns.append(Pattern(
                    name="errors",
                    description="Custom exception classes",
                    examples=[str(py_file.relative_to(self.project_path))],
                ))
                break

        return patterns[:1]

    def _detect_auth_patterns(self) -> list[Pattern]:
        """Detect authentication patterns."""
        patterns: list[Pattern] = []
        files = self._get_python_files()

        auth_indicators = {
            "python-jose": ["jose", "jwt.encode", "jwt.decode"],
            "PyJWT": ["import jwt", "jwt.encode", "jwt.decode"],
            "OAuth2": ["OAuth2PasswordBearer", "oauth2_scheme"],
            "API Keys": ["x-api-key", "api_key", "apikey"],
            "Basic Auth": ["HTTPBasic", "basic_auth"],
        }

        for py_file in files:
            try:
                content = py_file.read_text(encoding="utf-8")
            except Exception:
                continue

            for auth_type, indicators in auth_indicators.items():
                if any(ind in content for ind in indicators):
                    patterns.append(Pattern(
                        name="auth",
                        description=f"JWT via {auth_type}" if "jwt" in auth_type.lower() else auth_type,
                        examples=[str(py_file.relative_to(self.project_path))],
                    ))
                    return patterns[:1]

        return patterns

    def _detect_di_patterns(self) -> list[Pattern]:
        """Detect dependency injection patterns."""
        patterns: list[Pattern] = []
        files = self._get_python_files()

        for py_file in files:
            try:
                content = py_file.read_text(encoding="utf-8")
            except Exception:
                continue

            if "Depends(" in content:
                patterns.append(Pattern(
                    name="di",
                    description="FastAPI Depends()",
                    examples=[str(py_file.relative_to(self.project_path))],
                ))
                return patterns

            if "@inject" in content:
                patterns.append(Pattern(
                    name="di",
                    description="Decorator-based injection",
                    examples=[str(py_file.relative_to(self.project_path))],
                ))
                return patterns

            if "container" in content.lower() and "get(" in content:
                patterns.append(Pattern(
                    name="di",
                    description="Container-based DI",
                    examples=[str(py_file.relative_to(self.project_path))],
                ))
                return patterns

        return patterns

    def _detect_test_patterns(self) -> list[Pattern]:
        """Detect testing patterns."""
        patterns: list[Pattern] = []
        test_files: list[Path] = []

        for py_file in self.project_path.rglob("test*.py"):
            if not self._should_skip(py_file):
                test_files.append(py_file)
        for py_file in self.project_path.rglob("*_test.py"):
            if not self._should_skip(py_file):
                test_files.append(py_file)

        if not test_files:
            return patterns

        for test_file in test_files[:10]:
            try:
                content = test_file.read_text(encoding="utf-8")
            except Exception:
                continue

            if "@pytest.fixture" in content:
                patterns.append(Pattern(
                    name="tests",
                    description="Pytest with fixtures",
                    examples=[str(test_file.relative_to(self.project_path))],
                ))
                return patterns

            if "unittest.TestCase" in content:
                patterns.append(Pattern(
                    name="tests",
                    description="unittest TestCase classes",
                    examples=[str(test_file.relative_to(self.project_path))],
                ))
                return patterns

            if "def test_" in content:
                patterns.append(Pattern(
                    name="tests",
                    description="Pytest function-based tests",
                    examples=[str(test_file.relative_to(self.project_path))],
                ))
                return patterns

        return patterns

    def _detect_async_patterns(self) -> list[Pattern]:
        """Detect async/await patterns."""
        patterns: list[Pattern] = []
        files = self._get_python_files()
        async_count = 0

        for py_file in files:
            try:
                content = py_file.read_text(encoding="utf-8")
                tree = ast.parse(content)
            except Exception:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.AsyncFunctionDef):
                    async_count += 1

        if async_count > 5:
            patterns.append(Pattern(
                name="async",
                description=f"Async/await ({async_count}+ async functions)",
            ))

        return patterns

    def _detect_orm_patterns(self) -> list[Pattern]:
        """Detect ORM patterns."""
        patterns: list[Pattern] = []
        files = self._get_python_files()

        for py_file in files:
            try:
                content = py_file.read_text(encoding="utf-8")
            except Exception:
                continue

            if "declarative_base" in content or "DeclarativeBase" in content:
                patterns.append(Pattern(
                    name="orm",
                    description="SQLAlchemy declarative models",
                    examples=[str(py_file.relative_to(self.project_path))],
                ))
                return patterns

            if "class Meta:" in content and "models.Model" in content:
                patterns.append(Pattern(
                    name="orm",
                    description="Django ORM models",
                    examples=[str(py_file.relative_to(self.project_path))],
                ))
                return patterns

            if "peewee" in content.lower():
                patterns.append(Pattern(
                    name="orm",
                    description="Peewee ORM models",
                    examples=[str(py_file.relative_to(self.project_path))],
                ))
                return patterns

        return patterns
