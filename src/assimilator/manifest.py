"""Data contracts for the codebase manifest."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Language(Enum):
    """Supported programming languages."""
    PYTHON = "python"
    GDSCRIPT = "gdscript"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    UNKNOWN = "unknown"


@dataclass
class Component:
    """Represents a code component (class, service, model, etc.)."""
    name: str
    type: str
    location: str
    summary: str
    dependencies: list[str] = field(default_factory=list)
    exports: list[str] = field(default_factory=list)
    fields: list[str] = field(default_factory=list)
    methods: list[str] = field(default_factory=list)

    def to_compressed_dict(self) -> dict[str, Any]:
        """Return minimal dict representation."""
        result: dict[str, Any] = {
            "name": self.name,
            "type": self.type,
            "loc": self.location,
        }
        if self.fields:
            result["fields"] = self.fields
        if self.methods:
            result["methods"] = self.methods
        if self.summary:
            result["summary"] = self.summary
        return result


@dataclass
class Pattern:
    """Represents a detected coding pattern or convention."""
    name: str
    description: str
    examples: list[str] = field(default_factory=list)

    def to_compressed_dict(self) -> dict[str, str]:
        """Return minimal dict representation."""
        return {self.name: self.description}


@dataclass
class Manifest:
    """Complete manifest of a codebase for LLM context."""
    project_name: str
    language: Language
    stack: list[str] = field(default_factory=list)
    structure: dict[str, str] = field(default_factory=dict)
    components: list[Component] = field(default_factory=list)
    patterns: list[Pattern] = field(default_factory=list)
    entry_points: dict[str, str] = field(default_factory=dict)
    stats: dict[str, int] = field(default_factory=dict)
    git_info: dict[str, Any] = field(default_factory=dict)

    def to_compressed_dict(self) -> dict[str, Any]:
        """Output optimized for LLM context - minimal tokens."""
        result: dict[str, Any] = {
            "project": self.project_name,
            "lang": self.language.value,
        }

        if self.stack:
            result["stack"] = self.stack

        if self.structure:
            result["structure"] = self.structure

        if self.components:
            result["components"] = [c.to_compressed_dict() for c in self.components[:20]]

        if self.patterns:
            patterns_dict: dict[str, str] = {}
            for p in self.patterns:
                patterns_dict.update(p.to_compressed_dict())
            result["patterns"] = patterns_dict

        if self.entry_points:
            result["entry_points"] = self.entry_points

        if self.stats:
            result["stats"] = self.stats

        if self.git_info:
            result["git"] = self.git_info

        return result

    def to_full_dict(self) -> dict[str, Any]:
        """Return full dict representation for caching."""
        return {
            "project_name": self.project_name,
            "language": self.language.value,
            "stack": self.stack,
            "structure": self.structure,
            "components": [
                {
                    "name": c.name,
                    "type": c.type,
                    "location": c.location,
                    "summary": c.summary,
                    "dependencies": c.dependencies,
                    "exports": c.exports,
                    "fields": c.fields,
                    "methods": c.methods,
                }
                for c in self.components
            ],
            "patterns": [
                {"name": p.name, "description": p.description, "examples": p.examples}
                for p in self.patterns
            ],
            "entry_points": self.entry_points,
            "stats": self.stats,
            "git_info": self.git_info,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Manifest":
        """Reconstruct Manifest from dict (for cache loading)."""
        return cls(
            project_name=data.get("project_name", "unknown"),
            language=Language(data.get("language", "unknown")),
            stack=data.get("stack", []),
            structure=data.get("structure", {}),
            components=[
                Component(
                    name=c["name"],
                    type=c["type"],
                    location=c["location"],
                    summary=c.get("summary", ""),
                    dependencies=c.get("dependencies", []),
                    exports=c.get("exports", []),
                    fields=c.get("fields", []),
                    methods=c.get("methods", []),
                )
                for c in data.get("components", [])
            ],
            patterns=[
                Pattern(
                    name=p["name"],
                    description=p["description"],
                    examples=p.get("examples", []),
                )
                for p in data.get("patterns", [])
            ],
            entry_points=data.get("entry_points", {}),
            stats=data.get("stats", {}),
            git_info=data.get("git_info", {}),
        )
