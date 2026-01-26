"""Spec-driven development contracts and data structures."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal


class SpecTier(Enum):
    """Classification of spec complexity and scope."""

    HOTFIX = "hotfix"
    FEATURE = "feature"
    SYSTEM = "system"


@dataclass
class ValidationConfig:
    """Configuration for validating implementations against specs."""

    tests: str
    typecheck: str | None = None
    lint: str | None = None
    success_criteria: dict[str, Any] = field(default_factory=lambda: {"all_tests_pass": True})


@dataclass
class SpecValidationResult:
    """Result of validating a spec document."""

    is_valid: bool
    spec: "SpecDocument | None"
    errors: list[str]


@dataclass
class SpecDocument:
    """Complete specification document for a feature or system."""

    name: str
    description: str
    tier: SpecTier
    interface: list[str]
    must_do: list[str]
    must_not_do: list[str]
    edge_cases: dict[str, str]
    preconditions: list[str]
    postconditions: list[str]
    invariants: list[str]
    validation: ValidationConfig
    target_path: str | None = None

    def to_prompt_context(self) -> str:
        """Serialize spec to string for inclusion in CLI prompt."""
        lines = [
            f"# Specification: {self.name}",
            f"Tier: {self.tier.value.upper()}",
            "",
            f"## Description",
            self.description,
            "",
        ]

        if self.interface:
            lines.append("## Interface")
            for sig in self.interface:
                lines.append(f"- {sig}")
            lines.append("")

        if self.must_do:
            lines.append("## Must Do")
            for req in self.must_do:
                lines.append(f"- {req}")
            lines.append("")

        if self.must_not_do:
            lines.append("## Must Not Do")
            for constraint in self.must_not_do:
                lines.append(f"- {constraint}")
            lines.append("")

        if self.edge_cases:
            lines.append("## Edge Cases")
            for case, outcome in self.edge_cases.items():
                lines.append(f"- {case} → {outcome}")
            lines.append("")

        if self.preconditions:
            lines.append("## Preconditions")
            for pre in self.preconditions:
                lines.append(f"- {pre}")
            lines.append("")

        if self.postconditions:
            lines.append("## Postconditions")
            for post in self.postconditions:
                lines.append(f"- {post}")
            lines.append("")

        if self.invariants:
            lines.append("## Invariants")
            for inv in self.invariants:
                lines.append(f"- {inv}")
            lines.append("")

        lines.append("## Validation")
        lines.append(f"- Tests: {self.validation.tests}")
        if self.validation.typecheck:
            lines.append(f"- Typecheck: {self.validation.typecheck}")
        if self.validation.lint:
            lines.append(f"- Lint: {self.validation.lint}")

        if self.target_path:
            lines.append("")
            lines.append(f"## Target Path")
            lines.append(self.target_path)

        return "\n".join(lines)


@dataclass
class PhaseRequest:
    """Request for a single phase execution."""

    phase: Literal["tests", "impl"]
    prompt: str
    spec: SpecDocument
    test_path: str | None
