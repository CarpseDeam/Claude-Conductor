"""Auto-documentation utilities."""

from pathlib import Path


def ensure_doc_structure(project_path: Path) -> None:
    """Create docs directory and files if missing."""
    docs_dir = project_path / "docs"
    docs_dir.mkdir(exist_ok=True)

    files = {
        "ARCHITECTURE.md": "# Architecture\n\n",
        "API.md": "# API Reference\n\n",
        "CHANGELOG.md": "# Changelog\n\n## [Unreleased]\n\n"
    }

    for filename, default_content in files.items():
        path = docs_dir / filename
        if not path.exists():
            path.write_text(default_content, encoding="utf-8")
