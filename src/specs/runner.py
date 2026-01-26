"""Single-phase spec execution runner."""

from pathlib import Path

from .contracts import PhaseRequest, SpecDocument
from .prompts import SpecPromptBuilder


class SpecPhaseRunner:
    """Orchestrates single-phase spec execution.

    This class prepares a unified phase request that gui_viewer.py uses for execution.
    It does NOT execute CLI commands directly - that's gui_viewer's job.

    Single phase: implement first, then write tests to verify.
    """

    def __init__(self, spec: SpecDocument, project_path: Path) -> None:
        if spec is None:
            raise TypeError("spec cannot be None")
        self.spec = spec
        self.project_path = project_path
        self.prompt_builder = SpecPromptBuilder()

    def get_request(self) -> PhaseRequest:
        """Get request for unified spec execution.

        Returns a PhaseRequest containing prompt for both implementation and tests.
        """
        prompt = self.prompt_builder.build_prompt(self.spec)
        return PhaseRequest(
            phase="impl",
            prompt=prompt,
            spec=self.spec,
            test_path=None,
        )

    def complete(self, success: bool) -> None:
        """Mark execution complete.

        Args:
            success: Whether the execution completed successfully.
        """
        pass
