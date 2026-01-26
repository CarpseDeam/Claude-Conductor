"""Unified dispatch handler."""
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from specs import SpecParser, SpecPromptBuilder
from specs.runner import SpecPhaseRunner


class DispatchMode(Enum):
    SPEC = "spec"
    PROSE = "prose"


@dataclass
class DispatchRequest:
    """Dispatch request with detected mode."""
    content: str
    project_path: Path
    cli: str
    model: str | None
    mode: DispatchMode
    spec_name: str | None = None
    phase_runner: SpecPhaseRunner | None = None


class DispatchHandler:
    """Handles dispatch routing and prompt building."""

    SPEC_MARKER = "## Spec:"

    def __init__(self) -> None:
        self.spec_parser = SpecParser()
        self.prompt_builder = SpecPromptBuilder()

    def prepare(
        self,
        content: str,
        project_path: Path,
        cli: str = "claude",
        model: str | None = None,
    ) -> DispatchRequest:
        """Prepare dispatch request, detecting mode from content."""
        mode = self._detect_mode(content)
        spec_name = None
        phase_runner = None

        if mode == DispatchMode.SPEC:
            spec = self.spec_parser.parse(content)
            spec_name = spec.name
            phase_runner = SpecPhaseRunner(spec, project_path)

        return DispatchRequest(
            content=content,
            project_path=project_path,
            cli=cli,
            model=model,
            mode=mode,
            spec_name=spec_name,
            phase_runner=phase_runner,
        )

    def build_prompt(self, request: DispatchRequest, system_prompt: str) -> str:
        """Build the full prompt for CLI execution (phase 1 for spec mode)."""
        if request.mode == DispatchMode.SPEC and request.phase_runner:
            phase1_request = request.phase_runner.get_phase1_request()
            prompt = phase1_request.prompt
        elif request.mode == DispatchMode.SPEC:
            spec = self.spec_parser.parse(request.content)
            prompt = self.prompt_builder.build_phase1_prompt(spec)
        else:
            prompt = request.content

        return f"{prompt}\n\n{system_prompt}"

    def build_phase2_prompt(self, request: DispatchRequest, test_path: str, system_prompt: str) -> str | None:
        """Build the phase 2 prompt for implementation."""
        if request.mode != DispatchMode.SPEC or not request.phase_runner:
            return None

        request.phase_runner.complete_phase1(success=True, test_path=test_path)
        phase2_request = request.phase_runner.get_phase2_request()
        if not phase2_request:
            return None

        return f"{phase2_request.prompt}\n\n{system_prompt}"

    def get_test_path(self, request: DispatchRequest) -> str | None:
        """Get the expected test path for spec mode."""
        if request.mode != DispatchMode.SPEC or not request.phase_runner:
            return None
        return request.phase_runner.infer_test_path()

    def _detect_mode(self, content: str) -> DispatchMode:
        """Detect dispatch mode from content."""
        stripped = content.strip()
        if stripped.startswith(self.SPEC_MARKER):
            return DispatchMode.SPEC
        return DispatchMode.PROSE
