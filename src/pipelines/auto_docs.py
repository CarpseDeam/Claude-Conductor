"""Auto-documentation utilities."""

from pathlib import Path

DOC_PLACEHOLDERS = {
    "CHANGELOG.md": "# Changelog\n\nAll notable changes to this project.\n",
    "ARCHITECTURE.md": "# Architecture\n\nSystem architecture documentation.\n",
    "API.md": "# API Reference\n\nAPI documentation.\n",
}


def ensure_doc_structure(project_path: Path) -> None:
    """Create docs/ directory and placeholder documentation files."""
    docs_dir = project_path / "docs"
    docs_dir.mkdir(exist_ok=True)

    for filename, content in DOC_PLACEHOLDERS.items():
        filepath = docs_dir / filename
        if not filepath.exists():
            filepath.write_text(content, encoding="utf-8")
