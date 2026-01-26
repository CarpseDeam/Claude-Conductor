"""Codebase mapper for generating project context."""
from dataclasses import dataclass, field
from pathlib import Path

from .detector import StackDetector, StackInfo
from .git_info import GitInfoExtractor, RecentCommit
from .parser import PythonParser, ModuleInfo


@dataclass
class FileInfo:
    """Info about a single file."""
    path: str
    purpose: str
    lines: int = 0
    module_info: ModuleInfo | None = None


@dataclass
class DirectoryInfo:
    """Info about a directory."""
    path: str
    purpose: str
    file_count: int = 0


@dataclass
class CodebaseMap:
    """Complete codebase map."""
    project_name: str
    stack: StackInfo
    directories: list[DirectoryInfo]
    key_files: list[FileInfo]
    entry_points: dict[str, str]
    stats: dict[str, int]
    dependencies: dict[str, list[str]] = field(default_factory=dict)
    recent_commits: list[RecentCommit] = field(default_factory=list)
    uncommitted: list[str] = field(default_factory=list)

    def to_markdown(self) -> str:
        """Render map as markdown for LLM context."""
        lines = [
            f"# {self.project_name}",
            "",
            f"**Language:** {self.stack.language}",
        ]

        if self.stack.frameworks:
            lines.append(f"**Frameworks:** {', '.join(self.stack.frameworks)}")
        if self.stack.tools:
            lines.append(f"**Tools:** {', '.join(self.stack.tools)}")

        lines.extend(["", "## Structure", ""])
        for d in self.directories:
            lines.append(f"- `{d.path}/` - {d.purpose} ({d.file_count} files)")

        lines.extend(["", "## Key Files", ""])
        for f in self.key_files:
            lines.append(f"- `{f.path}` - {f.purpose}")

        lines.extend(["", "## Module Details", ""])
        for f in self.key_files:
            if f.module_info:
                has_public = (
                    any(not m.is_private for c in f.module_info.classes for m in c.methods) or
                    any(not fn.is_private for fn in f.module_info.functions)
                )
                if not has_public and not f.module_info.docstring:
                    continue

                lines.append(f"### `{f.path}`")
                if f.module_info.docstring:
                    doc = f.module_info.docstring.split('\n\n')[0].strip()
                    lines.append(f"_{doc}_")
                    lines.append("")

                for cls in f.module_info.classes:
                    methods = [m.name for m in cls.methods if not m.is_private][:5]
                    if methods:
                        lines.append(f"**{cls.name}**: {', '.join(methods)}")

                public_funcs = [fn.signature for fn in f.module_info.functions if not fn.is_private]
                if public_funcs:
                    lines.append(f"**Functions**: `{', '.join(public_funcs[:5])}`")

                lines.append("")

        if self.dependencies:
            lines.extend(["", "## Dependencies", ""])
            for module, imports in sorted(self.dependencies.items()):
                lines.append(f"- `{module}` -> {', '.join(imports)}")

        if self.uncommitted:
            lines.extend(["", "## Uncommitted Changes", ""])
            for f in self.uncommitted[:10]:
                lines.append(f"- `{f}`")

        if self.recent_commits:
            lines.extend(["", "## Recent Changes", ""])
            for commit in self.recent_commits:
                files_str = ", ".join(commit.files[:3])
                if len(commit.files) > 3:
                    files_str += f" +{len(commit.files) - 3} more"
                lines.append(f"- **{commit.hash}**: {commit.message}")
                if files_str:
                    lines.append(f"  Files: {files_str}")

        if self.entry_points:
            lines.extend(["", "## Entry Points", ""])
            for task, location in self.entry_points.items():
                lines.append(f"- **{task}:** {location}")

        lines.extend([
            "",
            "## Stats",
            "",
            f"- Files: {self.stats.get('files', 0)}",
            f"- Directories: {self.stats.get('dirs', 0)}",
            f"- Lines: {self.stats.get('lines', 0)}",
        ])

        return "\n".join(lines)


class CodebaseMapper:
    """Maps a codebase to compressed context."""

    SKIP_DIRS: set[str] = {
        '.git', '.venv', 'venv', 'node_modules', '__pycache__',
        '.idea', '.vscode', 'dist', 'build', '.eggs', '.tox',
        '.mypy_cache', '.pytest_cache', '.conductor', '.ruff_cache',
        'htmlcov', '.coverage', 'addons', 'target', 'out', 'bin',
    }

    DIR_PURPOSES: dict[str, str] = {
        'src': 'Source code',
        'lib': 'Library code',
        'app': 'Application code',
        'api': 'API routes',
        'routes': 'Route handlers',
        'models': 'Data models',
        'schemas': 'Data schemas',
        'services': 'Business logic',
        'domain': 'Domain logic',
        'utils': 'Utilities',
        'helpers': 'Helper functions',
        'tests': 'Tests',
        'test': 'Tests',
        'docs': 'Documentation',
        'scripts': 'Scripts',
        'config': 'Configuration',
        'migrations': 'Database migrations',
        'static': 'Static assets',
        'templates': 'Templates',
        'components': 'UI components',
        'pages': 'Page components',
        'hooks': 'React hooks',
        'scenes': 'Godot scenes',
        'autoload': 'Godot autoloads',
    }

    KEY_FILE_PATTERNS: dict[str, str] = {
        'main.py': 'Entry point',
        'app.py': 'Application entry',
        'server.py': 'Server entry',
        'cli.py': 'CLI entry',
        'config.py': 'Configuration',
        'settings.py': 'Settings',
        'models.py': 'Data models',
        'schemas.py': 'Data schemas',
        'routes.py': 'Route handlers',
        'views.py': 'View handlers',
        'services.py': 'Business logic',
        'utils.py': 'Utilities',
        'constants.py': 'Constants',
        'exceptions.py': 'Custom exceptions',
        'types.py': 'Type definitions',
        'contracts.py': 'Data contracts',
        'pyproject.toml': 'Project config',
        'package.json': 'Package config',
        'Cargo.toml': 'Project config',
        'go.mod': 'Project config',
        'README.md': 'Documentation',
        'project.godot': 'Godot project',
    }

    MAX_SHALLOW_DEPTH: int = 2
    MAX_KEY_FILES: int = 30

    def __init__(self, project_path: Path | str) -> None:
        self.project_path = Path(project_path).resolve()
        self.detector = StackDetector()
        self.python_parser = PythonParser()
        self.git_extractor = GitInfoExtractor()

    def map(self) -> CodebaseMap:
        """Generate codebase map with AST parsing for key files."""
        stack = self.detector.detect(self.project_path)
        directories = self._list_directories_shallow()
        key_files = self._identify_key_files_fast()
        key_files = self._enrich_with_ast(key_files)
        entry_points = self._infer_entry_points(stack, directories)

        return CodebaseMap(
            project_name=self.project_path.name,
            stack=stack,
            directories=sorted(directories, key=lambda d: d.path),
            key_files=key_files,
            entry_points=entry_points,
            stats={
                'files': len(key_files),
                'dirs': len(directories),
                'lines': sum(f.lines for f in key_files),
            },
        )

    def _list_directories_shallow(self) -> list[DirectoryInfo]:
        """List directories up to MAX_SHALLOW_DEPTH levels deep."""
        directories: list[DirectoryInfo] = []

        try:
            for item in self.project_path.iterdir():
                if not item.is_dir() or item.name in self.SKIP_DIRS or item.name.startswith('.'):
                    continue

                purpose = self.DIR_PURPOSES.get(item.name.lower(), 'Project files')
                directories.append(DirectoryInfo(item.name, purpose))

                for sub_item in item.iterdir():
                    if not sub_item.is_dir() or sub_item.name in self.SKIP_DIRS or sub_item.name.startswith('.'):
                        continue
                    rel_path = f"{item.name}/{sub_item.name}"
                    sub_purpose = self.DIR_PURPOSES.get(sub_item.name.lower(), 'Project files')
                    directories.append(DirectoryInfo(rel_path, sub_purpose))
        except PermissionError:
            pass

        return directories

    def _identify_key_files_fast(self) -> list[FileInfo]:
        """Find key files by name pattern only. No file reading, no AST."""
        key_files: list[FileInfo] = []
        seen_names: set[str] = set()

        for name, purpose in self.KEY_FILE_PATTERNS.items():
            for match in self.project_path.glob(f"**/{name}"):
                if self._should_skip_path(match):
                    continue
                rel_path = str(match.relative_to(self.project_path))
                if rel_path not in seen_names:
                    seen_names.add(rel_path)
                    key_files.append(FileInfo(rel_path, purpose))
                if len(key_files) >= self.MAX_KEY_FILES:
                    return key_files

        return key_files

    def _should_skip_path(self, path: Path) -> bool:
        """Check if path contains any skip directories."""
        return any(part in self.SKIP_DIRS for part in path.parts)

    def _enrich_with_ast(self, files: list[FileInfo]) -> list[FileInfo]:
        """Add AST parsing and line counts to key files."""
        enriched: list[FileInfo] = []

        for f in files:
            full_path = self.project_path / f.path

            if full_path.suffix == '.py' and full_path.exists():
                module_info = self.python_parser.parse(full_path)
                lines = self._count_lines(full_path)
                enriched.append(FileInfo(f.path, f.purpose, lines, module_info))
            elif full_path.exists():
                lines = self._count_lines(full_path)
                enriched.append(FileInfo(f.path, f.purpose, lines))
            else:
                enriched.append(f)

        return enriched

    def _count_lines(self, path: Path) -> int:
        """Count lines in file."""
        try:
            return sum(1 for _ in path.open('rb'))
        except Exception:
            return 0

    def _build_dependency_graph(self, files: list[FileInfo]) -> dict[str, list[str]]:
        """Build dependency graph from parsed modules."""
        all_paths = {f.path for f in files}
        dependencies: dict[str, list[str]] = {}

        for f in files:
            if f.module_info and f.module_info.imports:
                internal_imports = [
                    imp for imp in f.module_info.imports
                    if self._is_internal_import(imp, all_paths)
                ]
                if internal_imports:
                    dependencies[f.path] = internal_imports

        return dependencies

    def _is_internal_import(self, module: str, all_paths: set[str]) -> bool:
        """Check if import is from this project."""
        parts = module.split('.')
        return any(any(part in path for part in parts) for path in all_paths)

    def _infer_entry_points(self, stack: StackInfo, directories: list[DirectoryInfo]) -> dict[str, str]:
        """Infer where to add new code."""
        entry_points: dict[str, str] = {}
        dir_names = {d.path.split('/')[-1].lower() for d in directories}

        if stack.language == "python":
            if "api" in dir_names or "routes" in dir_names:
                entry_points["New route"] = "src/api/ or src/routes/"
            if "models" in dir_names:
                entry_points["New model"] = "src/models/"
            if "services" in dir_names:
                entry_points["New service"] = "src/services/"
            if "tests" in dir_names or "test" in dir_names:
                entry_points["New test"] = "tests/"

        elif stack.language == "gdscript":
            if "scenes" in dir_names:
                entry_points["New scene"] = "scenes/"
            if "scripts" in dir_names:
                entry_points["New script"] = "scripts/"
            if "autoload" in dir_names:
                entry_points["New autoload"] = "autoload/"

        return entry_points
