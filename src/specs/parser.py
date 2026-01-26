"""Parser for markdown spec format."""

import re

from .contracts import SpecDocument, SpecTier, ValidationConfig


class SpecParser:
    """Parses compact markdown specs into SpecDocument."""

    _TIER_PATTERN = re.compile(r"##\s*Spec:\s*(\w+)\s*\[(\w+)\]")
    _SECTION_PATTERN = re.compile(r"^###\s+(.+)$", re.MULTILINE)
    _EDGE_CASE_PATTERN = re.compile(r"^-\s*(.+?)\s*(?:→|->)+\s*(.+)$")
    _BULLET_PATTERN = re.compile(r"^-\s+(.+)$")

    def parse(self, markdown: str) -> SpecDocument:
        """Parse markdown spec into structured document."""
        name, tier = self._parse_header(markdown)
        description = self._extract_description(markdown)
        sections = self._split_sections(markdown)

        validation_content = sections.get("Validation", "")
        validation = self._parse_validation(validation_content)

        return SpecDocument(
            name=name,
            description=description,
            tier=tier,
            interface=self._extract_section(sections.get("Interface", "")),
            must_do=self._extract_section(sections.get("Must Do", "")),
            must_not_do=self._extract_section(sections.get("Must Not Do", "")),
            edge_cases=self._extract_edge_cases(sections.get("Edge Cases", "")),
            preconditions=self._extract_section(sections.get("Preconditions", "")),
            postconditions=self._extract_section(sections.get("Postconditions", "")),
            invariants=self._extract_section(sections.get("Invariants", "")),
            validation=validation,
            target_path=self._extract_target_path(sections.get("Target Path", "")),
        )

    def _parse_header(self, content: str) -> tuple[str, SpecTier]:
        """Extract name and tier from spec header."""
        match = self._TIER_PATTERN.search(content)
        if not match:
            raise ValueError(
                "Invalid spec header. Expected format: '## Spec: FeatureName [TIER]'"
            )

        name = match.group(1)
        tier_str = match.group(2).upper()

        try:
            tier = SpecTier[tier_str]
        except KeyError:
            valid_tiers = ", ".join(t.name for t in SpecTier)
            raise ValueError(f"Invalid tier '{tier_str}'. Valid tiers: {valid_tiers}")

        return name, tier

    def _extract_description(self, content: str) -> str:
        """Extract description from content between header and first section."""
        header_match = self._TIER_PATTERN.search(content)
        if not header_match:
            return ""

        start = header_match.end()
        section_match = self._SECTION_PATTERN.search(content, start)
        end = section_match.start() if section_match else len(content)

        description = content[start:end].strip()
        return description

    def _split_sections(self, content: str) -> dict[str, str]:
        """Split content into sections by ### headers."""
        sections: dict[str, str] = {}
        matches = list(self._SECTION_PATTERN.finditer(content))

        for i, match in enumerate(matches):
            section_name = match.group(1).strip()
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            sections[section_name] = content[start:end].strip()

        return sections

    def _extract_section(self, content: str) -> list[str]:
        """Extract bullet points from a section."""
        if not content:
            return []

        items = []
        for line in content.split("\n"):
            line = line.strip()
            match = self._BULLET_PATTERN.match(line)
            if match:
                items.append(match.group(1).strip())

        return items

    def _extract_edge_cases(self, content: str) -> dict[str, str]:
        """Parse edge cases in format: '- case → outcome'."""
        if not content:
            return {}

        edge_cases: dict[str, str] = {}
        for line in content.split("\n"):
            line = line.strip()
            if not line.startswith("-"):
                continue

            line_content = line[1:].strip()
            match = self._EDGE_CASE_PATTERN.match(f"- {line_content}")
            if match:
                case = match.group(1).strip()
                outcome = match.group(2).strip()
                edge_cases[case] = outcome

        return edge_cases

    def _parse_validation(self, content: str) -> ValidationConfig:
        """Parse validation block, return defaults if not present."""
        if not content:
            return ValidationConfig(tests="pytest tests/ -v")

        yaml_match = re.search(r"```ya?ml\s*\n(.+?)```", content, re.DOTALL)
        if yaml_match:
            yaml_content = yaml_match.group(1)
        else:
            yaml_content = content

        config: dict[str, str | None] = {
            "tests": None,
            "typecheck": None,
            "lint": None,
        }

        for line in yaml_content.split("\n"):
            line = line.strip()
            if ":" not in line:
                continue

            key, _, value = line.partition(":")
            key = key.strip().lower()
            value = value.strip()

            if key in config:
                config[key] = value if value else None

        tests = config["tests"]
        if not tests:
            raise ValueError("Validation block must specify 'tests' command")

        return ValidationConfig(
            tests=tests,
            typecheck=config["typecheck"],
            lint=config["lint"],
        )

    def _extract_target_path(self, content: str) -> str | None:
        """Extract target path from section."""
        if not content:
            return None

        for line in content.split("\n"):
            line = line.strip()
            if line and not line.startswith("#"):
                return line

        return None
