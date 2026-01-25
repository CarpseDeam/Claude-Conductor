"""Core orchestrator for codebase assimilation."""

import logging
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

    def assimilate(self, force_refresh: bool = False) -> Manifest:
        """Run all applicable analyzers and merge results into Manifest."""
        if self.use_cache and not force_refresh:
            cached = self.cache.get_cached(self.project_path)
            if cached:
                self.logger.info("Using cached manifest")
                return cached

        self.logger.info("Analyzing project: %s", self.project_path)

        results: dict[str, Any] = {
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

        for analyzer in self.analyzers:
            analyzer_results = analyzer.safe_analyze()
            self._merge_results(results, analyzer_results)

        for extractor in self.extractors:
            extractor_results = extractor.safe_extract()
            self._merge_results(results, extractor_results)

        results["entry_points"] = self._infer_entry_points(results)

        manifest = self._build_manifest(results)

        if self.use_cache:
            self.cache.save(self.project_path, manifest)

        return manifest

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
