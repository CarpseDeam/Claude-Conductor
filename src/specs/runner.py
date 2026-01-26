"""Two-phase spec execution runner."""

from pathlib import Path
from typing import Literal

from .contracts import PhaseRequest, SpecDocument
from .prompts import SpecPromptBuilder


class SpecPhaseRunner:
    """Orchestrates two-phase spec execution without direct subprocess calls.

    This class prepares phase requests that gui_viewer.py uses for execution.
    It does NOT execute CLI commands directly - that's gui_viewer's job.

    Phase 1 generates tests in fresh context.
    Phase 2 implements against those tests in fresh context.
    """

    def __init__(self, spec: SpecDocument, project_path: Path) -> None:
        self.spec = spec
        self.project_path = project_path
        self.prompt_builder = SpecPromptBuilder()
        self.current_phase: Literal["tests", "impl"] = "tests"
        self.test_path: str | None = None

    def get_phase1_request(self) -> PhaseRequest:
        """Get request for phase 1 (tests only)."""
        prompt = self.prompt_builder.build_phase1_prompt(self.spec)
        return PhaseRequest(
            phase="tests",
            prompt=prompt,
            spec=self.spec,
            test_path=None,
        )

    def complete_phase1(self, success: bool, test_path: str) -> None:
        """Mark phase 1 complete, store test path for phase 2."""
        if success:
            self.test_path = test_path
            self.current_phase = "impl"

    def get_phase2_request(self) -> PhaseRequest | None:
        """Get request for phase 2 (implementation).

        Returns None if phase 1 failed or test_path not set.
        """
        if self.test_path is None:
            return None
        prompt = self.prompt_builder.build_phase2_prompt(self.spec, self.test_path)
        return PhaseRequest(
            phase="impl",
            prompt=prompt,
            spec=self.spec,
            test_path=self.test_path,
        )

    def infer_test_path(self) -> str:
        """Infer test file path from spec."""
        name_slug = self.spec.name.lower().replace(" ", "_").replace("-", "_")
        return f"tests/test_{name_slug}.py"
