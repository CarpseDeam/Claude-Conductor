"""Stack and pattern detection from project files."""
from dataclasses import dataclass
from pathlib import Path


@dataclass
class StackInfo:
    """Detected technology stack."""
    language: str
    frameworks: list[str]
    tools: list[str]
    package_manager: str | None


class StackDetector:
    """Detects project stack from config files."""

    CONFIG_SIGNALS: dict[str, tuple[str, dict[str, str]]] = {
        "pyproject.toml": ("python", {
            "fastapi": "FastAPI",
            "flask": "Flask",
            "django": "Django",
            "pytest": "pytest",
            "ruff": "ruff",
            "mypy": "mypy",
            "pydantic": "Pydantic",
        }),
        "requirements.txt": ("python", {
            "fastapi": "FastAPI",
            "flask": "Flask",
            "django": "Django",
            "pytest": "pytest",
        }),
        "package.json": ("javascript", {
            "react": "React",
            "vue": "Vue",
            "next": "Next.js",
            "express": "Express",
            "typescript": "TypeScript",
        }),
        "project.godot": ("gdscript", {}),
        "Cargo.toml": ("rust", {}),
        "go.mod": ("go", {}),
    }

    def detect(self, project_path: Path) -> StackInfo:
        """Detect stack from config files. Fast: only reads configs."""
        language = "unknown"
        frameworks: list[str] = []
        tools: list[str] = []
        package_manager: str | None = None

        for config_file, (lang, signals) in self.CONFIG_SIGNALS.items():
            config_path = project_path / config_file
            if config_path.exists():
                language = lang
                package_manager = self._infer_package_manager(config_file)

                try:
                    content = config_path.read_text(encoding="utf-8").lower()
                    for keyword, name in signals.items():
                        if keyword in content:
                            if name in ("pytest", "ruff", "mypy"):
                                tools.append(name)
                            else:
                                frameworks.append(name)
                except Exception:
                    pass

        return StackInfo(
            language=language,
            frameworks=sorted(set(frameworks)),
            tools=sorted(set(tools)),
            package_manager=package_manager,
        )

    def _infer_package_manager(self, config_file: str) -> str | None:
        """Infer package manager from config file."""
        managers = {
            "pyproject.toml": "pip",
            "requirements.txt": "pip",
            "package.json": "npm",
            "Cargo.toml": "cargo",
            "go.mod": "go",
        }
        return managers.get(config_file)
