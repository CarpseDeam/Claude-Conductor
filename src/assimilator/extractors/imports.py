"""Extractor for building dependency graphs from imports."""

import ast
from pathlib import Path
from typing import Any

from .base import BaseExtractor


class ImportsExtractor(BaseExtractor):
    """Extracts import relationships to build dependency graph."""

    def can_extract(self) -> bool:
        """Check if project has Python files."""
        return any(self.project_path.rglob("*.py"))

    def extract(self) -> dict[str, Any]:
        """Extract import relationships."""
        modules = self._discover_modules()
        graph = self._build_dependency_graph(modules)
        external = self._identify_external_deps(modules)
        circular = self._detect_circular_dependencies(graph)

        return {
            "dependency_graph": graph,
            "external_dependencies": external,
            "circular_dependencies": circular,
        }

    def _discover_modules(self) -> dict[str, Path]:
        """Discover all Python modules in the project."""
        modules: dict[str, Path] = {}

        for py_file in self.project_path.rglob("*.py"):
            if self._should_skip(py_file):
                continue

            rel_path = py_file.relative_to(self.project_path)
            module_name = self._path_to_module(rel_path)
            if module_name:
                modules[module_name] = py_file

        return modules

    def _path_to_module(self, path: Path) -> str:
        """Convert file path to module name."""
        parts = list(path.parts)
        if not parts:
            return ""

        if parts[-1] == "__init__.py":
            parts = parts[:-1]
        elif parts[-1].endswith(".py"):
            parts[-1] = parts[-1][:-3]

        return ".".join(parts)

    def _should_skip(self, path: Path) -> bool:
        """Check if path should be skipped."""
        skip_dirs = {"__pycache__", ".venv", "venv", "node_modules", ".git", "dist", "build"}
        return any(part in skip_dirs for part in path.parts)

    def _build_dependency_graph(self, modules: dict[str, Path]) -> dict[str, list[str]]:
        """Build internal dependency graph."""
        graph: dict[str, list[str]] = {}
        module_names = set(modules.keys())

        for module_name, file_path in modules.items():
            imports = self._extract_imports(file_path)
            internal_imports = [imp for imp in imports if self._is_internal(imp, module_names)]
            graph[module_name] = internal_imports

        return graph

    def _extract_imports(self, file_path: Path) -> list[str]:
        """Extract all imports from a Python file."""
        imports: list[str] = []

        try:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(file_path))
        except Exception:
            return imports

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
                    for alias in node.names:
                        imports.append(f"{node.module}.{alias.name}")

        return imports

    def _is_internal(self, import_name: str, module_names: set[str]) -> bool:
        """Check if import is internal to the project."""
        if import_name in module_names:
            return True

        for module in module_names:
            if import_name.startswith(module + "."):
                return True
            if module.startswith(import_name + "."):
                return True

        return False

    def _identify_external_deps(self, modules: dict[str, Path]) -> list[str]:
        """Identify external dependencies."""
        all_imports: set[str] = set()
        module_names = set(modules.keys())

        for file_path in modules.values():
            imports = self._extract_imports(file_path)
            for imp in imports:
                if not self._is_internal(imp, module_names):
                    top_level = imp.split(".")[0]
                    if not self._is_stdlib(top_level):
                        all_imports.add(top_level)

        return sorted(all_imports)

    def _is_stdlib(self, module_name: str) -> bool:
        """Check if module is part of Python standard library."""
        stdlib = {
            "abc", "ast", "asyncio", "base64", "collections", "contextlib",
            "copy", "dataclasses", "datetime", "decimal", "enum", "functools",
            "hashlib", "http", "importlib", "io", "itertools", "json", "logging",
            "math", "os", "pathlib", "pickle", "random", "re", "shutil", "socket",
            "sqlite3", "string", "subprocess", "sys", "tempfile", "threading",
            "time", "typing", "unittest", "urllib", "uuid", "warnings", "xml",
            "zipfile", "zlib", "fnmatch", "glob", "secrets", "statistics",
        }
        return module_name in stdlib

    def _detect_circular_dependencies(self, graph: dict[str, list[str]]) -> list[tuple[str, str]]:
        """Detect circular dependencies in the graph."""
        circular: list[tuple[str, str]] = []
        visited: set[str] = set()

        for module in graph:
            if module in visited:
                continue

            path: list[str] = []
            self._dfs_detect_cycle(module, graph, path, visited, circular)

        return circular[:10]

    def _dfs_detect_cycle(
        self,
        node: str,
        graph: dict[str, list[str]],
        path: list[str],
        visited: set[str],
        circular: list[tuple[str, str]],
    ) -> None:
        """DFS to detect cycles."""
        if node in path:
            idx = path.index(node)
            if len(path) > idx:
                circular.append((path[idx], node))
            return

        if node in visited:
            return

        path.append(node)
        for neighbor in graph.get(node, []):
            self._dfs_detect_cycle(neighbor, graph, path, visited, circular)
        path.pop()
        visited.add(node)
