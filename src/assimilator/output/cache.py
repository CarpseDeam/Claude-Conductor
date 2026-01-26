"""Cache for manifests with fast git-based and time-based validation."""

import json
import logging
import time
from pathlib import Path

from ..manifest import Manifest


class ManifestCache:
    """Caches manifests with fast validation via git HEAD or TTL fallback."""

    CACHE_DIR = ".conductor"
    CACHE_FILE = "manifest.json"
    META_FILE = "manifest.meta"
    CACHE_TTL_SECONDS = 300  # 5 minutes

    def __init__(self) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)

    def get_cached(self, project_path: Path) -> Manifest | None:
        """Return cached manifest if still valid. Fast path: <50ms."""
        start = time.perf_counter()
        cache_dir = project_path / self.CACHE_DIR
        cache_file = cache_dir / self.CACHE_FILE
        meta_file = cache_dir / self.META_FILE

        if not cache_file.exists():
            self.logger.debug("Cache miss: file not found (%.3fs)", time.perf_counter() - start)
            return None

        if not self._is_cache_valid(project_path, meta_file):
            self.logger.debug("Cache miss: validation failed (%.3fs)", time.perf_counter() - start)
            return None

        try:
            cache_data = json.loads(cache_file.read_text(encoding="utf-8"))
            manifest = Manifest.from_dict(cache_data)
            self.logger.debug("Cache hit (%.3fs)", time.perf_counter() - start)
            return manifest
        except Exception as e:
            self.logger.debug("Cache miss: %s (%.3fs)", e, time.perf_counter() - start)
            return None

    def _is_cache_valid(self, project_path: Path, meta_file: Path) -> bool:
        """Fast cache validation. Target: <50ms."""
        if not meta_file.exists():
            return False

        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))

            git_head = self._get_git_head(project_path)
            if git_head:
                return meta.get("git_head") == git_head

            cached_time = meta.get("timestamp", 0)
            return (time.time() - cached_time) < self.CACHE_TTL_SECONDS

        except Exception:
            return False

    def _get_git_head(self, project_path: Path) -> str | None:
        """Get current git HEAD hash. Fast: just reads .git/HEAD."""
        try:
            git_dir = project_path / ".git"
            if not git_dir.exists():
                return None

            head_file = git_dir / "HEAD"
            head_content = head_file.read_text(encoding="utf-8").strip()

            if head_content.startswith("ref: "):
                ref_path = head_content[5:]
                ref_file = git_dir / ref_path
                if ref_file.exists():
                    return ref_file.read_text(encoding="utf-8").strip()[:12]
            else:
                return head_content[:12]
        except Exception:
            return None

    def save(self, project_path: Path, manifest: Manifest) -> None:
        """Save manifest and metadata to cache."""
        start = time.perf_counter()
        cache_dir = project_path / self.CACHE_DIR
        cache_file = cache_dir / self.CACHE_FILE
        meta_file = cache_dir / self.META_FILE

        try:
            cache_dir.mkdir(exist_ok=True)
            self._ensure_gitignore(cache_dir)

            cache_data = manifest.to_full_dict()
            cache_file.write_text(json.dumps(cache_data, indent=2), encoding="utf-8")

            meta = {
                "timestamp": time.time(),
                "git_head": self._get_git_head(project_path),
            }
            meta_file.write_text(json.dumps(meta), encoding="utf-8")

            self.logger.debug("Cache saved (%.3fs)", time.perf_counter() - start)

        except Exception as e:
            self.logger.warning("Failed to save cache: %s", e)

    def invalidate(self, project_path: Path) -> None:
        """Invalidate cache for a project."""
        cache_dir = project_path / self.CACHE_DIR
        cache_file = cache_dir / self.CACHE_FILE
        meta_file = cache_dir / self.META_FILE

        try:
            if cache_file.exists():
                cache_file.unlink()
            if meta_file.exists():
                meta_file.unlink()
            self.logger.debug("Cache invalidated")
        except Exception as e:
            self.logger.warning("Failed to invalidate cache: %s", e)

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
