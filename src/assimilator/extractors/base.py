"""Abstract base class for extractors."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any
import logging


class BaseExtractor(ABC):
    """Base class for all code extractors."""

    def __init__(self, project_path: Path) -> None:
        """Initialize extractor with project path."""
        self.project_path = project_path
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def extract(self) -> dict[str, Any]:
        """Extract specific data from the project."""
        ...

    @abstractmethod
    def can_extract(self) -> bool:
        """Check if this extractor can operate on the project."""
        ...

    def safe_extract(self) -> dict[str, Any]:
        """Run extract with error handling for graceful degradation."""
        if not self.can_extract():
            self.logger.debug("Extractor not applicable for this project")
            return {}

        try:
            return self.extract()
        except Exception as e:
            self.logger.warning("Extraction failed: %s", e)
            return {}
