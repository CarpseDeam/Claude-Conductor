"""Extractor for classes, functions, and exports."""

import ast
from pathlib import Path
from typing import Any

from .base import BaseExtractor
from ..manifest import Component


class SymbolsExtractor(BaseExtractor):
    """Extracts class and function symbols from Python code."""

    def can_extract(self) -> bool:
        """Check if project has Python files."""
        return any(self.project_path.rglob("*.py"))

    def extract(self) -> dict[str, Any]:
        """Extract symbols from all Python files."""
        components: list[Component] = []

        for py_file in self.project_path.rglob("*.py"):
            if self._should_skip(py_file):
                continue

            file_components = self._extract_from_file(py_file)
            components.extend(file_components)

        return {"components": components[:100]}

    def _should_skip(self, path: Path) -> bool:
        """Check if path should be skipped."""
        skip_dirs = {"__pycache__", ".venv", "venv", "node_modules", ".git", "dist", "build"}
        return any(part in skip_dirs for part in path.parts)

    def _extract_from_file(self, file_path: Path) -> list[Component]:
        """Extract components from a single file."""
        components: list[Component] = []

        try:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(file_path))
        except Exception as e:
            self.logger.debug("Failed to parse %s: %s", file_path, e)
            return components

        rel_path = str(file_path.relative_to(self.project_path))
        exports = self._get_exports(tree)

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                component = self._extract_class(node, rel_path, exports)
                if component:
                    components.append(component)

            elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                component = self._extract_function(node, rel_path, exports)
                if component:
                    components.append(component)

        return components

    def _get_exports(self, tree: ast.Module) -> set[str]:
        """Get __all__ exports from module."""
        exports: set[str] = set()

        for node in ast.iter_child_nodes(tree):
            if not isinstance(node, ast.Assign):
                continue

            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    if isinstance(node.value, ast.List | ast.Tuple):
                        for elt in node.value.elts:
                            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                exports.add(elt.value)

        return exports

    def _extract_class(self, node: ast.ClassDef, location: str, exports: set[str]) -> Component | None:
        """Extract class component."""
        if node.name.startswith("_") and node.name not in exports:
            return None

        component_type = self._infer_class_type(node)
        methods = self._get_public_methods(node)
        fields = self._get_class_fields(node)
        bases = [self._get_name(base) for base in node.bases]
        summary = self._generate_class_summary(node, component_type, bases)

        return Component(
            name=node.name,
            type=component_type,
            location=location,
            summary=summary,
            dependencies=bases,
            exports=[node.name] if node.name in exports else [],
            fields=fields,
            methods=methods,
        )

    def _extract_function(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef, location: str, exports: set[str]
    ) -> Component | None:
        """Extract function component."""
        if node.name.startswith("_") and node.name not in exports:
            return None

        decorators = [self._get_decorator_name(d) for d in node.decorator_list]
        component_type = self._infer_function_type(node, decorators)
        summary = self._generate_function_summary(node, component_type, decorators)

        return Component(
            name=node.name,
            type=component_type,
            location=location,
            summary=summary,
            exports=[node.name] if node.name in exports else [],
            methods=[],
            fields=[],
        )

    def _infer_class_type(self, node: ast.ClassDef) -> str:
        """Infer class type from decorators and naming."""
        decorators = [self._get_decorator_name(d) for d in node.decorator_list]

        if "dataclass" in decorators:
            return "dataclass"
        if any(d in decorators for d in ["BaseModel", "pydantic"]):
            return "model"

        name_lower = node.name.lower()
        if name_lower.endswith("model"):
            return "model"
        if name_lower.endswith("service"):
            return "service"
        if name_lower.endswith("controller"):
            return "controller"
        if name_lower.endswith("handler"):
            return "handler"
        if name_lower.endswith("factory"):
            return "factory"
        if name_lower.endswith("repository"):
            return "repository"
        if name_lower.endswith("error") or name_lower.endswith("exception"):
            return "exception"

        bases = [self._get_name(b) for b in node.bases]
        if any("Exception" in b or "Error" in b for b in bases):
            return "exception"
        if any("ABC" in b or "Protocol" in b for b in bases):
            return "interface"

        return "class"

    def _infer_function_type(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef, decorators: list[str]
    ) -> str:
        """Infer function type from decorators and naming."""
        if any(d in decorators for d in ["route", "get", "post", "put", "delete", "patch", "api_route"]):
            return "route"
        if any(d in decorators for d in ["app", "router"]):
            return "route"
        if "staticmethod" in decorators:
            return "static_method"
        if "classmethod" in decorators:
            return "class_method"
        if "property" in decorators:
            return "property"
        if "fixture" in decorators:
            return "test_fixture"

        if node.name.startswith("test_"):
            return "test"

        return "function"

    def _get_public_methods(self, node: ast.ClassDef) -> list[str]:
        """Get public method names from class."""
        methods: list[str] = []
        for item in node.body:
            if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
                if not item.name.startswith("_") or item.name == "__init__":
                    methods.append(item.name)
        return methods[:10]

    def _get_class_fields(self, node: ast.ClassDef) -> list[str]:
        """Get class field names."""
        fields: list[str] = []

        for item in node.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                fields.append(item.target.id)

        for item in node.body:
            if isinstance(item, ast.FunctionDef) and item.name == "__init__":
                for stmt in ast.walk(item):
                    if isinstance(stmt, ast.Assign):
                        for target in stmt.targets:
                            if isinstance(target, ast.Attribute):
                                if isinstance(target.value, ast.Name) and target.value.id == "self":
                                    fields.append(target.attr)

        return list(dict.fromkeys(fields))[:10]

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

    def _generate_class_summary(self, node: ast.ClassDef, ctype: str, bases: list[str]) -> str:
        """Generate one-liner summary for class."""
        if bases:
            return f"{ctype} extending {', '.join(bases[:2])}"
        return ctype

    def _generate_function_summary(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef, ftype: str, decorators: list[str]
    ) -> str:
        """Generate one-liner summary for function."""
        prefix = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
        return f"{prefix}{ftype}"
