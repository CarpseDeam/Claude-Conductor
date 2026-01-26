"""Validation function for spec documents."""

from __future__ import annotations

import re

from .contracts import SpecDocument, SpecTier, SpecValidationResult, ValidationConfig


def validate_spec(markdown: str) -> SpecValidationResult:
    """Validate a markdown spec and return structured result.

    Unlike SpecParser.parse(), this function never raises exceptions.
    Instead, it returns a SpecValidationResult with validation errors.

    Args:
        markdown: The markdown spec content to validate.

    Returns:
        SpecValidationResult with is_valid=True and populated spec for valid input,
        or is_valid=False and populated errors for invalid input.
    """
    errors: list[str] = []

    # Check header
    tier_pattern = re.compile(r"##\s*Spec:\s*(\w+)\s*\[(\w+)\]")
    header_match = tier_pattern.search(markdown)

    name: str | None = None
    tier: SpecTier | None = None

    if not header_match:
        errors.append(
            "Invalid spec header. Expected format: '## Spec: FeatureName [TIER]'"
        )
    else:
        name = header_match.group(1)
        tier_str = header_match.group(2).upper()

        try:
            tier = SpecTier[tier_str]
        except KeyError:
            valid_tiers = ", ".join(t.name for t in SpecTier)
            errors.append(f"Invalid tier '{tier_str}'. Valid tiers: {valid_tiers}")

    # Check validation block for tests command
    validation_error = _check_validation_block(markdown)
    if validation_error:
        errors.append(validation_error)

    # If any errors, return invalid result
    if errors:
        return SpecValidationResult(
            is_valid=False,
            spec=None,
            errors=errors,
        )

    # No errors - parse the full spec
    from .parser import SpecParser

    parser = SpecParser()
    spec = parser.parse(markdown)

    return SpecValidationResult(
        is_valid=True,
        spec=spec,
        errors=[],
    )


def _check_validation_block(markdown: str) -> str | None:
    """Check if validation block has required tests command.

    Returns error message if validation is missing tests, None otherwise.
    """
    section_pattern = re.compile(r"^###\s+(.+)$", re.MULTILINE)
    matches = list(section_pattern.finditer(markdown))

    # Find Validation section
    validation_content: str | None = None
    for i, match in enumerate(matches):
        section_name = match.group(1).strip()
        if section_name == "Validation":
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(markdown)
            validation_content = markdown[start:end].strip()
            break

    if validation_content is None:
        # No validation section - will use default, which is OK
        # But if there IS a validation section without tests, that's an error
        # Check if "Validation" is even mentioned
        if "### Validation" not in markdown:
            # Default validation will be used by parser, check header first
            return None

    if validation_content is not None:
        # Check for tests command in validation block
        yaml_match = re.search(r"```ya?ml\s*\n(.+?)```", validation_content, re.DOTALL)
        if yaml_match:
            yaml_content = yaml_match.group(1)
        else:
            yaml_content = validation_content

        has_tests = False
        for line in yaml_content.split("\n"):
            line = line.strip()
            if ":" not in line:
                continue
            key, _, value = line.partition(":")
            key = key.strip().lower()
            value = value.strip()
            if key == "tests" and value:
                has_tests = True
                break

        if not has_tests:
            return "Validation block must specify 'tests' command"

    return None
