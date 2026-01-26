"""Codebase mapper for generating project context."""
from dataclasses import dataclass
from pathlib import Path

from .detector import StackDetector, StackInfo
from .parser import PythonParser, ModuleInfo


@dataclass
class FileInfo:
    """Info about a single file."""
    path: str
    purpose: str
    lines: int
    module_info: ModuleInfo | None = None


@dataclass
class DirectoryInfo:
    """Info about a directory."""
    path: str
    purpose: str
    file_count: int


@dataclass
class CodebaseMap:
    """Complete codebase map."""
    project_name: str
    stack: StackInfo
    directories: list[DirectoryInfo]
    key_files: list[FileInfo]
    entry_points: dict[str, str]
    stats: dict[str, int]

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
                lines.append(f"### `{f.path}`")
                if f.module_info.docstring:
                    doc = f.module_info.docstring.split('\n\n')[0].strip()
                    lines.append(f"_{doc}_")
                    lines.append("")

                for cls in f.module_info.classes:
                    methods = [m.signature for m in cls.methods if not m.is_private][:5]
                    if methods:
                        lines.append(f"**{cls.name}**: `{', '.join(methods)}`")

                public_funcs = [fn.signature for fn in f.module_info.functions if not fn.is_private]
                if public_funcs:
                    lines.append(f"**Functions**: `{', '.join(public_funcs[:5])}`")

                lines.append("")

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

    SKIP_FILES: set[str] = {
        '.DS_Store', 'Thumbs.db', '.gitignore', '.gitattributes',
    }

    CODE_EXTENSIONS: set[str] = {
        '.py', '.js', '.ts', '.tsx', '.jsx', '.gd',
        '.java', '.go', '.rs', '.rb', '.php', '.cs',
        '.cpp', '.c', '.h', '.hpp', '.swift', '.kt',
        '.vue', '.svelte', '.md', '.json', '.yaml', '.toml',
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

    FILE_PURPOSES: dict[str, str] = {
        '__init__.py': 'Package init',
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
        'helpers.py': 'Helper functions',
        'constants.py': 'Constants',
        'exceptions.py': 'Custom exceptions',
        'types.py': 'Type definitions',
        'contracts.py': 'Data contracts',
        'conftest.py': 'Test fixtures',
        'pyproject.toml': 'Project config',
        'package.json': 'Package config',
        'README.md': 'Documentation',
        'project.godot': 'Godot project',
    }

    MAX_FILES: int = 1000
    MAX_KEY_FILES: int = 30

    def __init__(self, project_path: Path | str) -> None:
        self.project_path = Path(project_path).resolve()
        self.detector = StackDetector()
        self.python_parser = PythonParser()

    def map(self) -> CodebaseMap:
        """Generate codebase map. Synchronous, fast."""
        stack = self.detector.detect(self.project_path)

        directories: list[DirectoryInfo] = []
        all_files: list[FileInfo] = []
        total_lines = 0
        dir_count = 0

        for item in self._walk():
            if item.is_dir():
                dir_count += 1
                rel_path = str(item.relative_to(self.project_path))
                purpose = self._infer_dir_purpose(item.name)
                file_count = sum(1 for f in item.iterdir() if self._is_code_file(f))
                if file_count > 0 or purpose != "Project files":
                    directories.append(DirectoryInfo(rel_path, purpose, file_count))
            else:
                rel_path = str(item.relative_to(self.project_path))
                purpose = self._infer_file_purpose(item)
                lines = self._count_lines(item)
                total_lines += lines
                if item.suffix == '.py':
                    module_info = self.python_parser.parse(item)
                    file_info = FileInfo(rel_path, purpose, lines, module_info)
                else:
                    file_info = FileInfo(rel_path, purpose, lines)
                all_files.append(file_info)

                if len(all_files) >= self.MAX_FILES:
                    break

        key_files = self._select_key_files(all_files)
        entry_points = self._infer_entry_points(stack, directories)

        return CodebaseMap(
            project_name=self.project_path.name,
            stack=stack,
            directories=sorted(directories, key=lambda d: d.path),
            key_files=key_files,
            entry_points=entry_points,
            stats={
                'files': len(all_files),
                'dirs': dir_count,
                'lines': total_lines,
            },
        )

    def _walk(self):
        """Walk project directory, yielding files and dirs."""
        try:
            for item in self.project_path.rglob('*'):
                if self._should_skip(item):
                    continue
                yield item
        except PermissionError:
            pass

    def _should_skip(self, path: Path) -> bool:
        """Check if path should be skipped."""
        for part in path.parts:
            if part in self.SKIP_DIRS:
                return True

        if path.is_file():
            if path.name in self.SKIP_FILES:
                return True
            if path.name.startswith('.'):
                return True

        return False

    def _is_code_file(self, path: Path) -> bool:
        """Check if file is a code file."""
        return path.is_file() and path.suffix.lower() in self.CODE_EXTENSIONS

    def _infer_dir_purpose(self, name: str) -> str:
        """Infer directory purpose from name."""
        return self.DIR_PURPOSES.get(name.lower(), "Project files")

    def _infer_file_purpose(self, path: Path) -> str:
        """Infer file purpose from name and location."""
        name = path.name

        if name in self.FILE_PURPOSES:
            return self.FILE_PURPOSES[name]

        stem = path.stem.lower()
        if stem.startswith('test_') or stem.endswith('_test'):
            return "Tests"
        if 'route' in stem or 'endpoint' in stem:
            return "Route handlers"
        if 'model' in stem:
            return "Data models"
        if 'schema' in stem:
            return "Data schemas"
        if 'service' in stem:
            return "Business logic"
        if 'util' in stem or 'helper' in stem:
            return "Utilities"

        parent = path.parent.name.lower()
        if parent in self.DIR_PURPOSES:
            return self.DIR_PURPOSES[parent]

        return "Source code"

    def _count_lines(self, path: Path) -> int:
        """Count lines in file. Fast, handles errors."""
        try:
            return sum(1 for _ in path.open('rb'))
        except Exception:
            return 0

    def _select_key_files(self, files: list[FileInfo]) -> list[FileInfo]:
        """Select most important files for the map."""
        priority_purposes = {
            'Entry point', 'Application entry', 'Server entry',
            'CLI entry', 'Project config', 'Package config',
            'Configuration', 'Data models', 'Route handlers',
        }

        priority_files = [f for f in files if f.purpose in priority_purposes]
        other_files = [f for f in files if f.purpose not in priority_purposes]

        other_files.sort(key=lambda f: f.lines, reverse=True)

        result = priority_files + other_files
        return result[:self.MAX_KEY_FILES]

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
