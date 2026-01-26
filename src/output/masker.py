"""ObservationMasker - Compress verbose CLI output into minimal, actionable summaries."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class CommandType(Enum):
    """Type of CLI command for parsing strategy selection."""

    PYTEST = "pytest"
    MYPY = "mypy"
    LINT = "lint"
    GENERIC = "generic"


@dataclass
class ErrorLocation:
    """Structured representation of an error location."""

    file: str
    line: int
    message: str


@dataclass
class MaskedOutput:
    """Compressed output with pass/fail status and structured errors."""

    summary: str
    errors: list[ErrorLocation]
    raw_snippet: str | None


_MAX_SNIPPET_LINES = 20
_MAX_TOTAL_SIZE = 2000


def _truncate_to_last_n_lines(text: str, n: int) -> str:
    """Return the last n lines of text."""
    lines = text.strip().split("\n")
    return "\n".join(lines[-n:])


def _parse_pytest(raw: str) -> MaskedOutput:
    """Parse pytest output for pass/fail status and errors."""
    passed_match = re.search(r"(\d+)\s+passed", raw)
    failed_match = re.search(r"(\d+)\s+failed", raw)
    error_match = re.search(r"(\d+)\s+error", raw)

    passed = int(passed_match.group(1)) if passed_match else 0
    failed = int(failed_match.group(1)) if failed_match else 0
    errors_count = int(error_match.group(1)) if error_match else 0

    total_failures = failed + errors_count
    errors: list[ErrorLocation] = []

    if total_failures > 0:
        error_pattern = re.compile(
            r"FAILED\s+([^:\s]+)::(\w+)\s*-\s*(.+?)(?:\n|$)"
        )
        for match in error_pattern.finditer(raw):
            file_path = match.group(1)
            message = match.group(3).strip()
            line_match = re.search(rf"{re.escape(file_path)}:(\d+):", raw)
            line_num = int(line_match.group(1)) if line_match else 0
            errors.append(ErrorLocation(file=file_path, line=line_num, message=message))

        if not errors and error_match:
            err_pattern = re.compile(r"([^\s:]+\.py):(\d+):\s*(\w+Error.+?)(?:\n|$)")
            for match in err_pattern.finditer(raw):
                errors.append(
                    ErrorLocation(
                        file=match.group(1),
                        line=int(match.group(2)),
                        message=match.group(3).strip(),
                    )
                )

    if total_failures > 0:
        parts = []
        if failed:
            parts.append(f"{failed} failed")
        if errors_count:
            parts.append(f"{errors_count} error")
        if passed:
            parts.append(f"{passed} passed")
        summary = f"✗ {', '.join(parts)}"
        snippet = _truncate_to_last_n_lines(raw, _MAX_SNIPPET_LINES)
        return MaskedOutput(summary=summary, errors=errors, raw_snippet=snippet)

    if passed > 0:
        return MaskedOutput(
            summary=f"✓ {passed} passed", errors=[], raw_snippet=None
        )

    return MaskedOutput(
        summary="? Unknown pytest output",
        errors=[],
        raw_snippet=_truncate_to_last_n_lines(raw, _MAX_SNIPPET_LINES),
    )


def _parse_mypy(raw: str) -> MaskedOutput:
    """Parse mypy output for pass/fail status and errors."""
    if "Success" in raw:
        return MaskedOutput(summary="✓ mypy: Success", errors=[], raw_snippet=None)

    error_count_match = re.search(r"Found\s+(\d+)\s+error", raw)
    errors: list[ErrorLocation] = []

    error_pattern = re.compile(r"^([^\s:]+):(\d+):\s*error:\s*(.+?)(?:\s+\[|$)", re.MULTILINE)
    for match in error_pattern.finditer(raw):
        errors.append(
            ErrorLocation(
                file=match.group(1),
                line=int(match.group(2)),
                message=match.group(3).strip(),
            )
        )

    if error_count_match:
        count = int(error_count_match.group(1))
        return MaskedOutput(
            summary=f"✗ mypy: {count} errors",
            errors=errors,
            raw_snippet=_truncate_to_last_n_lines(raw, _MAX_SNIPPET_LINES),
        )

    if errors:
        return MaskedOutput(
            summary=f"✗ mypy: {len(errors)} errors",
            errors=errors,
            raw_snippet=_truncate_to_last_n_lines(raw, _MAX_SNIPPET_LINES),
        )

    return MaskedOutput(
        summary="? Unknown mypy output",
        errors=[],
        raw_snippet=_truncate_to_last_n_lines(raw, _MAX_SNIPPET_LINES),
    )


def _parse_lint(raw: str) -> MaskedOutput:
    """Parse lint output (flake8/ruff style) for errors."""
    errors: list[ErrorLocation] = []

    error_pattern = re.compile(r"^([^\s:]+):(\d+):\d+:\s*(E\d+\s+.+?)$", re.MULTILINE)
    for match in error_pattern.finditer(raw):
        errors.append(
            ErrorLocation(
                file=match.group(1),
                line=int(match.group(2)),
                message=match.group(3).strip(),
            )
        )

    if errors:
        return MaskedOutput(
            summary=f"✗ lint: {len(errors)} errors",
            errors=errors,
            raw_snippet=_truncate_to_last_n_lines(raw, _MAX_SNIPPET_LINES),
        )

    if raw.strip():
        return MaskedOutput(
            summary="✓ lint: clean",
            errors=[],
            raw_snippet=None,
        )

    return MaskedOutput(summary="No output", errors=[], raw_snippet=None)


def _parse_generic(raw: str) -> MaskedOutput:
    """Parse generic/unknown output."""
    if not raw.strip():
        return MaskedOutput(summary="No output", errors=[], raw_snippet=None)

    return MaskedOutput(
        summary="? Unknown output",
        errors=[],
        raw_snippet=_truncate_to_last_n_lines(raw, _MAX_SNIPPET_LINES),
    )


def _ensure_size_limit(output: MaskedOutput) -> MaskedOutput:
    """Ensure total output size is under the limit."""
    total_size = len(output.summary)
    total_size += sum(
        len(e.file) + len(str(e.line)) + len(e.message) for e in output.errors
    )
    if output.raw_snippet:
        total_size += len(output.raw_snippet)

    if total_size <= _MAX_TOTAL_SIZE:
        return output

    available = _MAX_TOTAL_SIZE - len(output.summary)
    errors_size = sum(
        len(e.file) + len(str(e.line)) + len(e.message) for e in output.errors
    )
    available -= errors_size

    if available > 0 and output.raw_snippet:
        truncated_snippet = output.raw_snippet[:available]
        return MaskedOutput(
            summary=output.summary,
            errors=output.errors,
            raw_snippet=truncated_snippet,
        )

    return MaskedOutput(
        summary=output.summary,
        errors=output.errors[:10],
        raw_snippet=None,
    )


def mask_output(raw: str, command_type: CommandType) -> MaskedOutput:
    """Compress verbose CLI output into minimal, actionable summary.

    Args:
        raw: The raw output string (stdout+stderr combined or separate)
        command_type: The type of command that produced the output

    Returns:
        MaskedOutput with summary, structured errors, and optional raw snippet
    """
    try:
        if not raw.strip():
            return MaskedOutput(summary="No output", errors=[], raw_snippet=None)

        if command_type == CommandType.PYTEST:
            result = _parse_pytest(raw)
        elif command_type == CommandType.MYPY:
            result = _parse_mypy(raw)
        elif command_type == CommandType.LINT:
            result = _parse_lint(raw)
        else:
            result = _parse_generic(raw)

        return _ensure_size_limit(result)

    except Exception:
        return MaskedOutput(
            summary="? Parse error",
            errors=[],
            raw_snippet=_truncate_to_last_n_lines(raw, _MAX_SNIPPET_LINES)
            if raw.strip()
            else None,
        )
