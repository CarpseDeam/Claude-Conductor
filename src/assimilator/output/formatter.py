"""Formatter for manifest output."""

import json
from typing import Any

from ..manifest import Manifest


class ManifestFormatter:
    """Formats manifests for different output targets."""

    TARGET_TOKENS = 2000
    CHARS_PER_TOKEN = 4
    MAX_MARKDOWN_CHARS = TARGET_TOKENS * CHARS_PER_TOKEN

    def to_json(self, manifest: Manifest, compact: bool = True) -> str:
        """Convert manifest to JSON string."""
        data = manifest.to_compressed_dict() if compact else manifest.to_full_dict()

        if compact:
            return json.dumps(data, separators=(",", ":"))
        return json.dumps(data, indent=2)

    def to_dict(self, manifest: Manifest, compact: bool = True) -> dict[str, Any]:
        """Convert manifest to dictionary."""
        return manifest.to_compressed_dict() if compact else manifest.to_full_dict()

    def estimate_tokens(self, manifest: Manifest) -> int:
        """Estimate token count for compressed manifest."""
        json_str = self.to_json(manifest, compact=True)
        return len(json_str) // self.CHARS_PER_TOKEN

    def trim_to_budget(self, manifest: Manifest, max_tokens: int | None = None) -> Manifest:
        """Trim manifest to fit within token budget."""
        max_tokens = max_tokens or self.TARGET_TOKENS

        current_tokens = self.estimate_tokens(manifest)
        if current_tokens <= max_tokens:
            return manifest

        trimmed = Manifest(
            project_name=manifest.project_name,
            language=manifest.language,
            stack=manifest.stack[:10],
            structure=dict(list(manifest.structure.items())[:8]),
            components=manifest.components[:15],
            patterns=manifest.patterns[:5],
            entry_points=dict(list(manifest.entry_points.items())[:5]),
            stats=manifest.stats,
            git_info={k: v for k, v in manifest.git_info.items() if k == "branch"},
        )

        if self.estimate_tokens(trimmed) > max_tokens:
            trimmed.components = trimmed.components[:10]
            trimmed.structure = dict(list(trimmed.structure.items())[:5])

        return trimmed

    def format_for_llm(self, manifest: Manifest) -> str:
        """Format manifest specifically for LLM consumption."""
        trimmed = self.trim_to_budget(manifest)
        return self.to_json(trimmed, compact=True)

    def to_markdown(self, manifest: Manifest) -> str:
        """Convert manifest to CLAUDE.md format."""
        trimmed = self.trim_to_budget(manifest)
        lines: list[str] = []

        lines.append(f"# {trimmed.project_name}")
        lines.append("")
        lines.append(f"**Language:** {trimmed.language.value}")
        if trimmed.stack:
            lines.append(f"**Stack:** {', '.join(trimmed.stack)}")
        lines.append("")

        lines.append("## Changelog")
        lines.append("")
        lines.append("_No changes recorded yet._")
        lines.append("")

        if trimmed.structure:
            lines.append("## Structure")
            lines.append("")
            for path, desc in trimmed.structure.items():
                lines.append(f"- `{path}` - {desc}")
            lines.append("")

        if trimmed.components:
            lines.append("## Components")
            lines.append("")
            lines.append("| Name | Type | Location | Summary |")
            lines.append("|------|------|----------|---------|")
            for comp in trimmed.components:
                summary = comp.summary[:50] + "..." if len(comp.summary) > 50 else comp.summary
                lines.append(f"| {comp.name} | {comp.type} | `{comp.location}` | {summary} |")
            lines.append("")

        if trimmed.patterns:
            lines.append("## Patterns")
            lines.append("")
            for pattern in trimmed.patterns:
                lines.append(f"- **{pattern.name}**: {pattern.description}")
            lines.append("")

        if trimmed.entry_points:
            lines.append("## Entry Points")
            lines.append("")
            for name, path in trimmed.entry_points.items():
                lines.append(f"- `{name}`: `{path}`")
            lines.append("")

        if trimmed.stats:
            lines.append("## Stats")
            lines.append("")
            for key, value in trimmed.stats.items():
                lines.append(f"- {key}: {value}")
            lines.append("")

        content = "\n".join(lines)
        if len(content) > self.MAX_MARKDOWN_CHARS:
            content = content[:self.MAX_MARKDOWN_CHARS - 3] + "..."
        return content
