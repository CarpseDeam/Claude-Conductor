"""Analyzer for Python projects."""

import ast
from pathlib import Path
from typing import Any

from .base import BaseAnalyzer
from ..manifest import Language


class PythonAnalyzer(BaseAnalyzer):
    """Analyzes Python projects using the ast module."""

    FRAMEWORK_INDICATORS: dict[str, list[str]] = {
        "FastAPI": ["fastapi", "from fastapi"],
        "Flask": ["flask", "from flask"],
        "Django": ["django", "from django"],
        "SQLAlchemy": ["sqlalchemy", "from sqlalchemy"],
        "Pydantic": ["pydantic", "from pydantic"],
        "Pytest": ["pytest", "from pytest"],
        "Alembic": ["alembic", "from alembic"],
        "Celery": ["celery", "from celery"],
        "Redis": ["redis", "from redis"],
        "httpx": ["httpx", "from httpx"],
        "requests": ["requests", "from requests"],
        "aiohttp": ["aiohttp", "from aiohttp"],
        "Click": ["click", "from click"],
        "Typer": ["typer", "from typer"],
    }

    PROJECT_FILES = ["pyproject.toml", "setup.py", "requirements.txt", "setup.cfg"]

    def can_analyze(self) -> bool:
        """Check if this is a Python project."""
        return any((self.project_path / f).exists() for f in self.PROJECT_FILES)

    def analyze(self) -> dict[str, Any]:
        """Analyze Python project."""
        stack = self._detect_stack()
        return {
            "language": Language.PYTHON,
            "stack": stack,
        }

    def _detect_stack(self) -> list[str]:
        """Detect frameworks and libraries used."""
        detected: set[str] = set()
        python_files = list(self.project_path.rglob("*.py"))[:100]

        for py_file in python_files:
            if self._should_skip(py_file):
                continue

            try:
                content = py_file.read_text(encoding="utf-8", errors="ignore")
                for framework, indicators in self.FRAMEWORK_INDICATORS.items():
                    if any(ind in content for ind in indicators):
                        detected.add(framework)
            except Exception:
                continue

        pyproject = self.project_path / "pyproject.toml"
        if pyproject.exists():
            detected.update(self._parse_pyproject(pyproject))

        requirements = self.project_path / "requirements.txt"
        if requirements.exists():
            detected.update(self._parse_requirements(requirements))

        return sorted(detected)

    def _should_skip(self, path: Path) -> bool:
        """Check if file should be skipped."""
        skip_dirs = {"__pycache__", ".venv", "venv", "node_modules", ".git", "dist", "build"}
        return any(part in skip_dirs for part in path.parts)

    def _parse_pyproject(self, path: Path) -> set[str]:
        """Parse pyproject.toml for dependencies."""
        detected: set[str] = set()
        try:
            content = path.read_text(encoding="utf-8")
            for framework, indicators in self.FRAMEWORK_INDICATORS.items():
                if any(ind.lower() in content.lower() for ind in indicators):
                    detected.add(framework)
        except Exception:
            pass
        return detected

    def _parse_requirements(self, path: Path) -> set[str]:
        """Parse requirements.txt for dependencies."""
        detected: set[str] = set()
        try:
            content = path.read_text(encoding="utf-8")
            lines = content.lower().splitlines()
            for line in lines:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                pkg_name = line.split("==")[0].split(">=")[0].split("<=")[0].split("[")[0]
                for framework in self.FRAMEWORK_INDICATORS:
                    if framework.lower() == pkg_name:
                        detected.add(framework)
        except Exception:
            pass
        return detected

    def parse_file(self, path: Path) -> dict[str, Any]:
        """Parse a Python file and extract metadata."""
        result: dict[str, Any] = {
            "classes": [],
            "functions": [],
            "imports": [],
            "decorators": [],
        }

        try:
            content = path.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(path))
        except Exception as e:
            self.logger.debug("Failed to parse %s: %s", path, e)
            return result

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                class_info = self._extract_class_info(node)
                result["classes"].append(class_info)

            elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                if not self._is_method(node, tree):
                    func_info = self._extract_function_info(node)
                    result["functions"].append(func_info)

            elif isinstance(node, ast.Import):
                for alias in node.names:
                    result["imports"].append(alias.name)

            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    result["imports"].append(node.module)

        return result

    def _extract_class_info(self, node: ast.ClassDef) -> dict[str, Any]:
        """Extract class information."""
        bases = [self._get_name(base) for base in node.bases]
        methods: list[str] = []
        fields: list[str] = []

        for item in node.body:
            if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
                if not item.name.startswith("_") or item.name == "__init__":
                    methods.append(item.name)
            elif isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                fields.append(item.target.id)

        return {
            "name": node.name,
            "bases": bases,
            "methods": methods,
            "fields": fields,
            "decorators": [self._get_decorator_name(d) for d in node.decorator_list],
        }

    def _extract_function_info(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> dict[str, Any]:
        """Extract function information."""
        return {
            "name": node.name,
            "args": [arg.arg for arg in node.args.args if arg.arg != "self"],
            "decorators": [self._get_decorator_name(d) for d in node.decorator_list],
            "is_async": isinstance(node, ast.AsyncFunctionDef),
        }

    def _get_name(self, node: ast.expr) -> str:
        """Get name from AST node."""
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return f"{self._get_name(node.value)}.{node.attr}"
        if isinstance(node, ast.Subscript):
            return self._get_name(node.value)
        return ""

    def _get_decorator_name(self, node: ast.expr) -> str:
        """Get decorator name."""
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        if isinstance(node, ast.Call):
            return self._get_decorator_name(node.func)
        return ""

    def _is_method(self, node: ast.FunctionDef | ast.AsyncFunctionDef, tree: ast.Module) -> bool:
        """Check if function is a method (inside a class)."""
        for parent in ast.walk(tree):
            if isinstance(parent, ast.ClassDef):
                if node in parent.body:
                    return True
        return False
