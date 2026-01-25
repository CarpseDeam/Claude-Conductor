"""Cache for manifests with invalidation on file changes."""

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from ..manifest import Manifest


class ManifestCache:
    """Caches manifests and invalidates on project changes."""

    CACHE_DIR = ".conductor"
    CACHE_FILE = "manifest.json"
    HASH_FILE = "manifest.hash"

    def __init__(self) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)

    def get_cached(self, project_path: Path) -> Manifest | None:
        """Return cached manifest if still valid."""
        cache_dir = project_path / self.CACHE_DIR
        cache_file = cache_dir / self.CACHE_FILE
        hash_file = cache_dir / self.HASH_FILE

        if not cache_file.exists() or not hash_file.exists():
            return None

        try:
            stored_hash = hash_file.read_text(encoding="utf-8").strip()
            current_hash = self._compute_hash(project_path)

            if stored_hash != current_hash:
                self.logger.debug("Cache invalidated: hash mismatch")
                return None

            cache_data = json.loads(cache_file.read_text(encoding="utf-8"))
            return Manifest.from_dict(cache_data)

        except Exception as e:
            self.logger.debug("Failed to read cache: %s", e)
            return None

    def save(self, project_path: Path, manifest: Manifest) -> None:
        """Save manifest to cache."""
        cache_dir = project_path / self.CACHE_DIR
        cache_file = cache_dir / self.CACHE_FILE
        hash_file = cache_dir / self.HASH_FILE

        try:
            cache_dir.mkdir(exist_ok=True)
            self._ensure_gitignore(cache_dir)

            cache_data = manifest.to_full_dict()
            cache_file.write_text(json.dumps(cache_data, indent=2), encoding="utf-8")

            current_hash = self._compute_hash(project_path)
            hash_file.write_text(current_hash, encoding="utf-8")

            self.logger.debug("Cache saved successfully")

        except Exception as e:
            self.logger.warning("Failed to save cache: %s", e)

    def invalidate(self, project_path: Path) -> None:
        """Invalidate cache for a project."""
        cache_dir = project_path / self.CACHE_DIR
        cache_file = cache_dir / self.CACHE_FILE
        hash_file = cache_dir / self.HASH_FILE

        try:
            if cache_file.exists():
                cache_file.unlink()
            if hash_file.exists():
                hash_file.unlink()
            self.logger.debug("Cache invalidated")
        except Exception as e:
            self.logger.warning("Failed to invalidate cache: %s", e)

    def _compute_hash(self, project_path: Path) -> str:
        """Compute hash based on file modification times."""
        hasher = hashlib.sha256()
        mtimes: list[tuple[str, float]] = []

        for path in self._get_tracked_files(project_path):
            try:
                rel_path = str(path.relative_to(project_path))
                mtime = path.stat().st_mtime
                mtimes.append((rel_path, mtime))
            except Exception:
                continue

        mtimes.sort(key=lambda x: x[0])

        for rel_path, mtime in mtimes:
            hasher.update(f"{rel_path}:{mtime}".encode())

        return hasher.hexdigest()[:16]

    def _get_tracked_files(self, project_path: Path, limit: int = 500) -> list[Path]:
        """Get files to track for cache invalidation."""
        tracked: list[Path] = []
        skip_dirs = {"__pycache__", ".venv", "venv", "node_modules", ".git", "dist", "build", self.CACHE_DIR}

        stack: list[Path] = [project_path]
        while stack and len(tracked) < limit:
            current = stack.pop()
            try:
                for item in current.iterdir():
                    if item.name in skip_dirs:
                        continue
                    if item.is_file():
                        if item.suffix in {".py", ".js", ".ts", ".json", ".toml", ".yaml", ".yml"}:
                            tracked.append(item)
                    elif item.is_dir():
                        stack.append(item)
            except PermissionError:
                continue

        return tracked

    def _ensure_gitignore(self, cache_dir: Path) -> None:
        """Ensure .conductor is in .gitignore."""
        project_path = cache_dir.parent
        gitignore = project_path / ".gitignore"

        if not gitignore.exists():
            return

        try:
            content = gitignore.read_text(encoding="utf-8")
            if self.CACHE_DIR not in content:
                with gitignore.open("a", encoding="utf-8") as f:
                    f.write(f"\n{self.CACHE_DIR}/\n")
        except Exception as e:
            self.logger.debug("Failed to update .gitignore: %s", e)
