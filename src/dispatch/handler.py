"""Unified dispatch handler."""
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DispatchRequest:
    """Dispatch request."""
    content: str
    project_path: Path
    cli: str
    model: str | None


class DispatchHandler:
    """Handles dispatch routing and prompt building."""

    def prepare(
        self,
        content: str,
        project_path: Path,
        cli: str = "claude",
        model: str | None = None,
    ) -> DispatchRequest:
        """Prepare dispatch request."""
        return DispatchRequest(
            content=content,
            project_path=project_path,
            cli=cli,
            model=model,
        )

    def build_prompt(self, request: DispatchRequest, system_prompt: str) -> str:
        """Build the full prompt for CLI execution."""
        return f"{request.content}\n\n{system_prompt}"
