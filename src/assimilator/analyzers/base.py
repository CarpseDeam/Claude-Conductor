"""Abstract base class for analyzers."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any
import logging


class BaseAnalyzer(ABC):
    """Base class for all codebase analyzers."""

    def __init__(self, project_path: Path) -> None:
        """Initialize analyzer with project path."""
        self.project_path = project_path
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def analyze(self) -> dict[str, Any]:
        """Analyze the project and return partial data for manifest."""
        ...

    @abstractmethod
    def can_analyze(self) -> bool:
        """Check if this analyzer applies to the project."""
        ...

    def safe_analyze(self) -> dict[str, Any]:
        """Run analyze with error handling for graceful degradation."""
        if not self.can_analyze():
            self.logger.debug("Analyzer not applicable for this project")
            return {}

        try:
            return self.analyze()
        except Exception as e:
            self.logger.warning("Analysis failed: %s", e)
            return {}
