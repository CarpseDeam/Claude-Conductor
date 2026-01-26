"""Python source file parser using AST."""
import ast
from dataclasses import dataclass
from pathlib import Path


@dataclass
class FunctionInfo:
    """Extracted function/method info."""
    name: str
    signature: str
    is_method: bool
    is_private: bool


@dataclass
class ClassInfo:
    """Extracted class info."""
    name: str
    docstring: str | None
    bases: list[str]
    methods: list[FunctionInfo]


@dataclass
class ModuleInfo:
    """Extracted module info."""
    path: str
    docstring: str | None
    classes: list[ClassInfo]
    functions: list[FunctionInfo]
    imports: list[str]

    def summary(self) -> str:
        """One-line summary of what's in this module."""
        parts = []
        if self.docstring:
            first_line = self.docstring.split('\n')[0].strip()
            if first_line:
                parts.append(first_line)

        if self.classes:
            class_names = [c.name for c in self.classes]
            parts.append(f"Classes: {', '.join(class_names)}")

        if self.functions:
            public_funcs = [f.name for f in self.functions if not f.is_private]
            if public_funcs:
                parts.append(f"Functions: {', '.join(public_funcs[:5])}")

        return " | ".join(parts) if parts else "No public interface"


class PythonParser:
    """Parses Python files to extract structure."""

    MAX_FILE_SIZE: int = 10240
    MAX_LINES: int = 500

    def parse(self, path: Path) -> ModuleInfo | None:
        """Parse a Python file. Returns None if parsing fails."""
        try:
            if path.stat().st_size > self.MAX_FILE_SIZE:
                return None

            source = path.read_text(encoding="utf-8")

            if source.count('\n') > self.MAX_LINES:
                return None

            tree = ast.parse(source)
        except (SyntaxError, UnicodeDecodeError, OSError):
            return None

        return ModuleInfo(
            path=str(path),
            docstring=ast.get_docstring(tree),
            classes=self._extract_classes(tree),
            functions=self._extract_functions(tree),
            imports=self._extract_imports(tree),
        )

    def _extract_classes(self, tree: ast.Module) -> list[ClassInfo]:
        """Extract class definitions."""
        classes = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                classes.append(ClassInfo(
                    name=node.name,
                    docstring=ast.get_docstring(node),
                    bases=[self._get_name(b) for b in node.bases],
                    methods=self._extract_methods(node),
                ))
        return classes

    def _extract_methods(self, class_node: ast.ClassDef) -> list[FunctionInfo]:
        """Extract methods from a class."""
        methods = []
        for node in ast.iter_child_nodes(class_node):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.append(FunctionInfo(
                    name=node.name,
                    signature=self._get_signature(node),
                    is_method=True,
                    is_private=node.name.startswith('_'),
                ))
        return methods

    def _extract_functions(self, tree: ast.Module) -> list[FunctionInfo]:
        """Extract top-level functions."""
        functions = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append(FunctionInfo(
                    name=node.name,
                    signature=self._get_signature(node),
                    is_method=False,
                    is_private=node.name.startswith('_'),
                ))
        return functions

    def _extract_imports(self, tree: ast.Module) -> list[str]:
        """Extract import statements. Filter to likely project imports."""
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module and not self._is_stdlib(node.module):
                    imports.append(node.module)
        return list(set(imports))[:10]

    def _get_signature(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
        """Build function signature string."""
        args = []

        for arg in node.args.args:
            arg_str = arg.arg
            if arg.annotation:
                arg_str += f": {self._get_annotation(arg.annotation)}"
            args.append(arg_str)

        if node.args.vararg:
            args.append(f"*{node.args.vararg.arg}")

        if node.args.kwarg:
            args.append(f"**{node.args.kwarg.arg}")

        sig = f"{node.name}({', '.join(args)})"

        if node.returns:
            sig += f" -> {self._get_annotation(node.returns)}"

        return sig

    def _get_annotation(self, node: ast.expr) -> str:
        """Convert annotation AST to string."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Constant):
            return repr(node.value)
        elif isinstance(node, ast.Subscript):
            value = self._get_annotation(node.value)
            slice_val = self._get_annotation(node.slice)
            return f"{value}[{slice_val}]"
        elif isinstance(node, ast.Attribute):
            return f"{self._get_annotation(node.value)}.{node.attr}"
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            left = self._get_annotation(node.left)
            right = self._get_annotation(node.right)
            return f"{left} | {right}"
        elif isinstance(node, ast.Tuple):
            elts = [self._get_annotation(e) for e in node.elts]
            return ", ".join(elts)
        else:
            return "..."

    def _get_name(self, node: ast.expr) -> str:
        """Get name from various node types."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_name(node.value)}.{node.attr}"
        return "?"

    def _is_stdlib(self, module: str) -> bool:
        """Check if module is likely stdlib."""
        stdlib = {
            'os', 'sys', 'json', 'logging', 'pathlib', 'typing',
            'dataclasses', 'enum', 'abc', 'functools', 'itertools',
            'collections', 'datetime', 'time', 're', 'ast', 'io',
            'subprocess', 'asyncio', 'concurrent', 'threading',
            'unittest', 'pytest', 'copy', 'hashlib', 'uuid',
        }
        root = module.split('.')[0]
        return root in stdlib
