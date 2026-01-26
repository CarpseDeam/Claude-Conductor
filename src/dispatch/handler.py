"""Unified dispatch handler."""
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from specs import SpecParser, SpecPromptBuilder


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

        if mode == DispatchMode.SPEC:
            spec = self.spec_parser.parse(content)
            spec_name = spec.name

        return DispatchRequest(
            content=content,
            project_path=project_path,
            cli=cli,
            model=model,
            mode=mode,
            spec_name=spec_name,
        )

    def build_prompt(self, request: DispatchRequest, system_prompt: str) -> str:
        """Build the full prompt for CLI execution."""
        if request.mode == DispatchMode.SPEC:
            spec = self.spec_parser.parse(request.content)
            prompt = self.prompt_builder.build_full_prompt(spec)
        else:
            prompt = request.content

        return f"{prompt}\n\n{system_prompt}"

    def _detect_mode(self, content: str) -> DispatchMode:
        """Detect dispatch mode from content."""
        stripped = content.strip()
        if stripped.startswith(self.SPEC_MARKER):
            return DispatchMode.SPEC
        return DispatchMode.PROSE
