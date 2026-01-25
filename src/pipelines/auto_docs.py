"""Auto-documentation utilities."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def ensure_doc_structure(project_path: Path) -> None:
    """Create docs directory and files if missing."""
    docs_dir = project_path / "docs"
    docs_dir.mkdir(exist_ok=True)

    project_name = project_path.name

    files = {
        docs_dir / "CHANGELOG.md": (
            f"# Changelog\n\n"
            f"All notable changes to {project_name}.\n\n"
            f"## [Unreleased]\n\n"
        ),
        docs_dir / "ARCHITECTURE.md": (
            f"# {project_name} Architecture\n\n"
            f"## Overview\n\n"
            f"_Auto-generated. Will be updated as project evolves._\n\n"
            f"## Components\n\n"
            f"## Data Flow\n\n"
        ),
        docs_dir / "API.md": (
            f"# {project_name} API Reference\n\n"
            f"_Auto-generated. Will be updated as project evolves._\n\n"
        ),
    }

    readme_path = project_path / "README.md"
    if not readme_path.exists():
        files[readme_path] = (
            f"# {project_name}\n\n"
            f"_Documentation auto-generated._\n\n"
            f"## Installation\n\n"
            f"## Usage\n\n"
        )

    for path, default_content in files.items():
        if not path.exists():
            path.write_text(default_content, encoding="utf-8")
            logger.info(f"Created {path}")
