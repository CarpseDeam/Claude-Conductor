"""Core orchestrator for codebase assimilation."""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from .manifest import Manifest, Language, Component, Pattern
from .analyzers.base import BaseAnalyzer
from .analyzers.structure_analyzer import StructureAnalyzer
from .analyzers.python_analyzer import PythonAnalyzer
from .analyzers.git_analyzer import GitAnalyzer
from .extractors.base import BaseExtractor
from .extractors.imports import ImportsExtractor
from .extractors.symbols import SymbolsExtractor
from .extractors.patterns import PatternsExtractor
from .output.cache import ManifestCache
from .output.formatter import ManifestFormatter


class Assimilator:
    """Orchestrates codebase analysis to generate a manifest."""

    MAX_WORKERS: int = 8
    MAX_FILES: int = 500
    MAX_FILE_SIZE: int = 100_000  # 100KB

    SKIP_DIRS: set[str] = {
        '.git', '.venv', 'venv', 'node_modules', '__pycache__',
        '.idea', '.vscode', 'dist', 'build', '.egg-info',
        'eggs', '.tox', '.mypy_cache', '.pytest_cache', '.conductor',
    }

    SKIP_EXTENSIONS: set[str] = {
        '.pyc', '.pyo', '.so', '.dll', '.exe', '.bin',
        '.png', '.jpg', '.jpeg', '.gif', '.ico', '.svg',
        '.mp3', '.wav', '.mp4', '.avi', '.mov',
        '.zip', '.tar', '.gz', '.rar',
        '.db', '.sqlite', '.sqlite3',
        '.lock', '.log',
    }

    CODE_EXTENSIONS: set[str] = {
        '.py', '.js', '.ts', '.tsx', '.jsx', '.gd',
        '.java', '.go', '.rs', '.rb', '.php', '.cs',
        '.cpp', '.c', '.h', '.hpp', '.swift', '.kt', '.scala',
        '.vue', '.svelte',
    }

    def __init__(self, project_path: Path | str, use_cache: bool = True) -> None:
        """Initialize assimilator with project path."""
        self.project_path = Path(project_path).resolve()
        self.use_cache = use_cache
        self.logger = logging.getLogger(self.__class__.__name__)
        self.cache = ManifestCache()
        self.formatter = ManifestFormatter()

        self.analyzers: list[BaseAnalyzer] = []
        self.extractors: list[BaseExtractor] = []

        self._register_defaults()

    def _register_defaults(self) -> None:
        """Register default analyzers and extractors."""
        self.analyzers = [
            StructureAnalyzer(self.project_path),
            PythonAnalyzer(self.project_path),
            GitAnalyzer(self.project_path),
        ]

        self.extractors = [
            ImportsExtractor(self.project_path),
            SymbolsExtractor(self.project_path),
            PatternsExtractor(self.project_path),
        ]

    def assimilate(self, force_refresh: bool = False, quick: bool = False) -> Manifest:
        """
        Run analyzers and merge results into Manifest.

        Args:
            force_refresh: Ignore cache and rebuild manifest.
            quick: Fast shallow analysis (structure + basic symbols only). Target: <2 seconds.
        """
        if self.use_cache and not force_refresh:
            cached = self.cache.get_cached(self.project_path)
            if cached:
                self.logger.info("Using cached manifest")
                return cached

        if quick:
            return self._quick_assimilate()

        return self._full_assimilate()

    def _quick_assimilate(self) -> Manifest:
        """Fast mode: structure + file list + basic detection. Target: <2 seconds."""
        start = time.perf_counter()
        self.logger.info("Quick analyzing project: %s", self.project_path)

        results: dict[str, Any] = self._init_results()

        t0 = time.perf_counter()
        structure_analyzer = StructureAnalyzer(self.project_path)
        self._merge_results(results, structure_analyzer.safe_analyze())
        self.logger.debug("StructureAnalyzer took %.3fs", time.perf_counter() - t0)

        t0 = time.perf_counter()
        git_analyzer = GitAnalyzer(self.project_path)
        self._merge_results(results, git_analyzer.safe_analyze())
        self.logger.debug("GitAnalyzer took %.3fs", time.perf_counter() - t0)

        t0 = time.perf_counter()
        python_analyzer = PythonAnalyzer(self.project_path)
        self._merge_results(results, python_analyzer.safe_analyze())
        self.logger.debug("PythonAnalyzer took %.3fs", time.perf_counter() - t0)

        results["entry_points"] = self._infer_entry_points(results)

        manifest = self._build_manifest(results)

        t0 = time.perf_counter()
        if self.use_cache:
            self.cache.save(self.project_path, manifest)
        self.logger.debug("Cache save took %.3fs", time.perf_counter() - t0)

        self.logger.info("Quick assimilate total: %.3fs", time.perf_counter() - start)
        return manifest

    def _full_assimilate(self) -> Manifest:
        """Full analysis with parallel file parsing."""
        self.logger.info("Full analyzing project: %s", self.project_path)

        results: dict[str, Any] = self._init_results()

        analyzer_results = self._run_analyzers_parallel()
        for ar in analyzer_results:
            self._merge_results(results, ar)

        extractor_results = self._run_extractors_parallel()
        for er in extractor_results:
            self._merge_results(results, er)

        results["entry_points"] = self._infer_entry_points(results)

        manifest = self._build_manifest(results)

        if self.use_cache:
            self.cache.save(self.project_path, manifest)

        return manifest

    def _init_results(self) -> dict[str, Any]:
        """Initialize empty results dict."""
        return {
            "project_name": self.project_path.name,
            "language": Language.UNKNOWN,
            "stack": [],
            "structure": {},
            "components": [],
            "patterns": [],
            "entry_points": {},
            "stats": {},
            "git_info": {},
        }

    def _run_analyzers_parallel(self) -> list[dict[str, Any]]:
        """Run all analyzers in parallel."""
        results: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as executor:
            futures = {executor.submit(a.safe_analyze): a for a in self.analyzers}
            for future in as_completed(futures):
                try:
                    result = future.result(timeout=5)
                    if result:
                        results.append(result)
                except Exception:
                    pass
        return results

    def _run_extractors_parallel(self) -> list[dict[str, Any]]:
        """Run all extractors in parallel."""
        results: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as executor:
            futures = {executor.submit(e.safe_extract): e for e in self.extractors}
            for future in as_completed(futures):
                try:
                    result = future.result(timeout=10)
                    if result:
                        results.append(result)
                except Exception:
                    pass
        return results

    def _should_skip(self, path: Path) -> bool:
        """Fast check if file/dir should be skipped."""
        if any(skip in path.parts for skip in self.SKIP_DIRS):
            return True
        if path.suffix.lower() in self.SKIP_EXTENSIONS:
            return True
        if path.is_file():
            try:
                if path.stat().st_size > self.MAX_FILE_SIZE:
                    return True
            except OSError:
                return True
        return False

    def collect_files(self, extensions: set[str] | None = None) -> list[Path]:
        """
        Collect files to analyze, respecting limits.

        Args:
            extensions: File extensions to include (e.g., {'.py', '.js'}). Defaults to CODE_EXTENSIONS.
        """
        if extensions is None:
            extensions = self.CODE_EXTENSIONS

        files: list[Path] = []
        try:
            for path in self.project_path.rglob('*'):
                if self._should_skip(path):
                    continue
                if path.is_file() and path.suffix.lower() in extensions:
                    files.append(path)
                if len(files) >= self.MAX_FILES:
                    self.logger.warning("Hit file limit (%d), sampling", self.MAX_FILES)
                    break
        except PermissionError:
            pass
        return files

    def _merge_results(self, target: dict[str, Any], source: dict[str, Any]) -> None:
        """Merge source results into target."""
        for key, value in source.items():
            if key not in target:
                target[key] = value
            elif isinstance(value, list):
                target[key].extend(value)
            elif isinstance(value, dict):
                target[key].update(value)
            elif key == "language" and isinstance(value, Language):
                if target[key] == Language.UNKNOWN:
                    target[key] = value

    def _build_manifest(self, results: dict[str, Any]) -> Manifest:
        """Build Manifest from aggregated results."""
        components = [
            c if isinstance(c, Component) else Component(**c)
            for c in results.get("components", [])
        ]

        patterns = [
            p if isinstance(p, Pattern) else Pattern(**p)
            for p in results.get("patterns", [])
        ]

        return Manifest(
            project_name=results["project_name"],
            language=results["language"],
            stack=sorted(set(results.get("stack", []))),
            structure=results.get("structure", {}),
            components=components,
            patterns=patterns,
            entry_points=results.get("entry_points", {}),
            stats=results.get("stats", {}),
            git_info=results.get("git_info", {}),
        )

    def _infer_entry_points(self, results: dict[str, Any]) -> dict[str, str]:
        """Infer common entry points based on detected patterns."""
        entry_points: dict[str, str] = {}
        structure = results.get("structure", {})
        language = results.get("language", Language.UNKNOWN)

        if language == Language.PYTHON:
            if any("api" in k.lower() or "route" in k.lower() for k in structure):
                entry_points["new_route"] = "src/api/{domain}.py or src/routes/{domain}.py"

            if any("model" in k.lower() for k in structure):
                entry_points["new_model"] = "src/models/{name}.py"

            if any("service" in k.lower() for k in structure):
                entry_points["new_service"] = "src/services/{name}.py"

            if "Alembic" in results.get("stack", []):
                entry_points["migration"] = "alembic revision --autogenerate"

        return entry_points

    def get_compressed_json(self, max_tokens: int | None = None) -> str:
        """Get manifest as compressed JSON for LLM context."""
        manifest = self.assimilate()
        if max_tokens:
            manifest = self.formatter.trim_to_budget(manifest, max_tokens)
        return self.formatter.to_json(manifest, compact=True)

    def get_token_estimate(self) -> int:
        """Estimate token count for the manifest."""
        manifest = self.assimilate()
        return self.formatter.estimate_tokens(manifest)

    def register_analyzer(self, analyzer: BaseAnalyzer) -> None:
        """Register a custom analyzer."""
        self.analyzers.append(analyzer)

    def register_extractor(self, extractor: BaseExtractor) -> None:
        """Register a custom extractor."""
        self.extractors.append(extractor)
