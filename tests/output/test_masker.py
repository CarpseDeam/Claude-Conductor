"""Tests for ObservationMasker - compresses verbose CLI output into actionable summaries."""

from __future__ import annotations

import pytest

from src.output.masker import (
    CommandType,
    ErrorLocation,
    MaskedOutput,
    mask_output,
)


# === FIXTURES ===


@pytest.fixture
def pytest_all_pass_output() -> str:
    return """============================= test session starts ==============================
platform linux -- Python 3.11.0, pytest-7.4.0
collected 15 items

tests/test_example.py::test_one PASSED
tests/test_example.py::test_two PASSED
tests/test_example.py::test_three PASSED

============================== 15 passed in 0.52s =============================="""


@pytest.fixture
def pytest_mixed_output() -> str:
    return """============================= test session starts ==============================
platform linux -- Python 3.11.0, pytest-7.4.0
collected 15 items

tests/test_example.py::test_one PASSED
tests/test_example.py::test_two FAILED
tests/test_example.py::test_three PASSED
tests/test_example.py::test_four FAILED
tests/test_example.py::test_five FAILED

=================================== FAILURES ===================================
_________________________________ test_two _________________________________

    def test_two():
>       assert 1 == 2
E       AssertionError: assert 1 == 2

tests/test_example.py:10: AssertionError
_________________________________ test_four _________________________________

    def test_four():
>       raise ValueError("oops")
E       ValueError: oops

tests/test_example.py:20: ValueError
_________________________________ test_five _________________________________

    def test_five():
>       assert func() == expected
E       AssertionError: assert None == 'value'

tests/test_other.py:15: AssertionError
=========================== short test summary info ============================
FAILED tests/test_example.py::test_two - AssertionError: assert 1 == 2
FAILED tests/test_example.py::test_four - ValueError: oops
FAILED tests/test_other.py::test_five - AssertionError: assert None == 'value'
========================= 3 failed, 12 passed in 1.23s ========================="""


@pytest.fixture
def mypy_success_output() -> str:
    return "Success: no issues found in 5 source files"


@pytest.fixture
def mypy_failure_output() -> str:
    return """src/main.py:10: error: Argument 1 to "func" has incompatible type "str"; expected "int"  [arg-type]
src/main.py:25: error: "None" has no attribute "value"  [attr-defined]
src/utils.py:5: error: Missing return statement  [return]
src/utils.py:42: error: Incompatible return value type  [return-value]
src/config.py:8: error: Name "undefined_var" is not defined  [name-defined]
Found 5 errors in 3 files (checked 10 source files)"""


@pytest.fixture
def lint_output_with_errors() -> str:
    return """src/main.py:10:5: E501 line too long (120 > 100 characters)
src/main.py:15:1: W291 trailing whitespace
src/utils.py:20:10: E302 expected 2 blank lines, found 1
src/utils.py:25:1: E303 too many blank lines (3)"""


# === BEHAVIOR TESTS (Must Do) ===


class TestPytestPassFailDetection:
    """Detect pass/fail from pytest output."""

    def test_detects_all_passed_pytest(self, pytest_all_pass_output: str) -> None:
        result = mask_output(pytest_all_pass_output, CommandType.PYTEST)
        assert "✓" in result.summary
        assert "15 passed" in result.summary
        assert len(result.errors) == 0

    def test_detects_failed_pytest(self, pytest_mixed_output: str) -> None:
        result = mask_output(pytest_mixed_output, CommandType.PYTEST)
        assert "✗" in result.summary
        assert "3 failed" in result.summary
        assert "12 passed" in result.summary

    def test_detects_error_count_pytest(self) -> None:
        output = """============================= test session starts ==============================
collected 5 items

tests/test_example.py::test_one ERROR

=================================== ERRORS ====================================
_________________ ERROR at setup of test_one _________________

    @pytest.fixture
    def broken_fixture():
>       raise RuntimeError("setup failed")
E       RuntimeError: setup failed

tests/conftest.py:5: RuntimeError
========================= 1 error in 0.10s ================================="""
        result = mask_output(output, CommandType.PYTEST)
        assert "✗" in result.summary
        assert "error" in result.summary.lower()


class TestMypyPassFailDetection:
    """Detect pass/fail from mypy output."""

    def test_detects_mypy_success(self, mypy_success_output: str) -> None:
        result = mask_output(mypy_success_output, CommandType.MYPY)
        assert "✓" in result.summary
        assert "Success" in result.summary or "success" in result.summary.lower()
        assert len(result.errors) == 0

    def test_detects_mypy_failure(self, mypy_failure_output: str) -> None:
        result = mask_output(mypy_failure_output, CommandType.MYPY)
        assert "✗" in result.summary
        assert "5" in result.summary
        assert len(result.errors) > 0


class TestErrorExtraction:
    """Extract file:line:message triples from error output."""

    def test_extracts_pytest_errors(self, pytest_mixed_output: str) -> None:
        result = mask_output(pytest_mixed_output, CommandType.PYTEST)
        assert len(result.errors) >= 1
        error_files = [e.file for e in result.errors]
        assert any("test_example.py" in f for f in error_files)

    def test_extracts_mypy_errors(self, mypy_failure_output: str) -> None:
        result = mask_output(mypy_failure_output, CommandType.MYPY)
        assert len(result.errors) == 5
        assert result.errors[0].file == "src/main.py"
        assert result.errors[0].line == 10
        assert "incompatible type" in result.errors[0].message.lower()

    def test_extracts_lint_errors(self, lint_output_with_errors: str) -> None:
        result = mask_output(lint_output_with_errors, CommandType.LINT)
        assert len(result.errors) >= 1
        assert any(e.file == "src/main.py" for e in result.errors)


class TestRawSnippetTruncation:
    """Truncate raw_snippet to last 20 lines of stderr/error output."""

    def test_truncates_to_20_lines_max(self) -> None:
        long_output = "\n".join([f"error line {i}" for i in range(100)])
        result = mask_output(long_output, CommandType.GENERIC)
        if result.raw_snippet:
            lines = result.raw_snippet.strip().split("\n")
            assert len(lines) <= 20

    def test_no_snippet_on_success(self, pytest_all_pass_output: str) -> None:
        result = mask_output(pytest_all_pass_output, CommandType.PYTEST)
        assert result.raw_snippet is None

    def test_snippet_present_on_failure(self, pytest_mixed_output: str) -> None:
        result = mask_output(pytest_mixed_output, CommandType.PYTEST)
        assert result.raw_snippet is not None


class TestEmptyErrorsOnSuccess:
    """Return empty errors list on success."""

    def test_no_errors_on_pytest_pass(self, pytest_all_pass_output: str) -> None:
        result = mask_output(pytest_all_pass_output, CommandType.PYTEST)
        assert result.errors == []

    def test_no_errors_on_mypy_success(self, mypy_success_output: str) -> None:
        result = mask_output(mypy_success_output, CommandType.MYPY)
        assert result.errors == []


class TestGracefulFallback:
    """Handle malformed/unexpected output gracefully."""

    def test_fallback_on_garbage_input(self) -> None:
        result = mask_output("random garbage text", CommandType.PYTEST)
        assert result.summary
        assert result.errors == [] or isinstance(result.errors, list)

    def test_fallback_on_binary_like_input(self) -> None:
        result = mask_output("\x00\x01\x02 binary data", CommandType.GENERIC)
        assert result.summary
        assert isinstance(result, MaskedOutput)


# === EDGE CASE TESTS ===


class TestEdgeCases:
    """Test all specified edge cases."""

    def test_empty_string_input(self) -> None:
        result = mask_output("", CommandType.GENERIC)
        assert result.summary == "No output"
        assert result.errors == []

    def test_all_tests_pass(self, pytest_all_pass_output: str) -> None:
        result = mask_output(pytest_all_pass_output, CommandType.PYTEST)
        assert "✓" in result.summary
        assert "15 passed" in result.summary
        assert result.errors == []
        assert result.raw_snippet is None

    def test_mixed_results(self, pytest_mixed_output: str) -> None:
        result = mask_output(pytest_mixed_output, CommandType.PYTEST)
        assert "✗" in result.summary
        assert "3 failed" in result.summary
        assert "12 passed" in result.summary
        assert len(result.errors) > 0
        assert result.raw_snippet is not None
        snippet_lines = result.raw_snippet.strip().split("\n")
        assert len(snippet_lines) <= 20

    def test_mypy_success(self, mypy_success_output: str) -> None:
        result = mask_output(mypy_success_output, CommandType.MYPY)
        assert "✓" in result.summary
        assert "mypy" in result.summary.lower() or "success" in result.summary.lower()
        assert result.errors == []

    def test_mypy_failure(self, mypy_failure_output: str) -> None:
        result = mask_output(mypy_failure_output, CommandType.MYPY)
        assert "✗" in result.summary
        assert "5" in result.summary
        assert len(result.errors) == 5

    def test_unrecognized_format(self) -> None:
        result = mask_output("some random output\nwith multiple lines", CommandType.GENERIC)
        assert "?" in result.summary or "Unknown" in result.summary
        assert result.raw_snippet is not None


# === CONTRACT TESTS ===


class TestPostconditions:
    """Verify postconditions are satisfied."""

    def test_summary_always_non_empty(self) -> None:
        inputs = ["", "random", "   \n\t  ", "\x00"]
        for inp in inputs:
            result = mask_output(inp, CommandType.GENERIC)
            assert result.summary
            assert len(result.summary) > 0

    def test_errors_contain_only_errors_not_warnings(
        self, lint_output_with_errors: str
    ) -> None:
        result = mask_output(lint_output_with_errors, CommandType.LINT)
        for error in result.errors:
            assert "W" not in error.message[:1]  # Not a warning code

    def test_total_output_under_2000_chars(self, pytest_mixed_output: str) -> None:
        result = mask_output(pytest_mixed_output, CommandType.PYTEST)
        total_size = len(result.summary)
        total_size += sum(
            len(e.file) + len(str(e.line)) + len(e.message) for e in result.errors
        )
        if result.raw_snippet:
            total_size += len(result.raw_snippet)
        assert total_size < 2000


class TestInvariants:
    """Verify invariants are preserved."""

    def test_never_returns_none(self) -> None:
        result = mask_output("anything", CommandType.GENERIC)
        assert result is not None
        assert isinstance(result, MaskedOutput)

    @pytest.mark.parametrize(
        "input_text,cmd_type",
        [
            ("", CommandType.GENERIC),
            ("garbage", CommandType.PYTEST),
            ("\x00\x01", CommandType.MYPY),
            ("normal text", CommandType.LINT),
        ],
    )
    def test_never_raises_exceptions(
        self, input_text: str, cmd_type: CommandType
    ) -> None:
        # Should not raise any exceptions
        result = mask_output(input_text, cmd_type)
        assert result is not None


# === CONSTRAINT TESTS (Must Not Do) ===


class TestMustNotConstraints:
    """Verify Must Not Do constraints are respected."""

    def test_no_full_raw_output_stored(self, pytest_mixed_output: str) -> None:
        result = mask_output(pytest_mixed_output, CommandType.PYTEST)
        # Full output is much longer than 20 lines
        if result.raw_snippet:
            assert len(result.raw_snippet) < len(pytest_mixed_output)

    def test_no_exceptions_on_unparseable(self) -> None:
        weird_inputs = [
            "\x00\x01\x02",
            "🎉🎊🎈" * 100,
            "a" * 10000,
            "\n" * 1000,
        ]
        for inp in weird_inputs:
            # Should not raise
            result = mask_output(inp, CommandType.GENERIC)
            assert result is not None


# === ADDITIONAL TESTS FOR ROBUSTNESS ===


class TestErrorLocationStructure:
    """Test ErrorLocation dataclass structure."""

    def test_error_location_has_required_fields(
        self, mypy_failure_output: str
    ) -> None:
        result = mask_output(mypy_failure_output, CommandType.MYPY)
        assert len(result.errors) > 0
        error = result.errors[0]
        assert hasattr(error, "file")
        assert hasattr(error, "line")
        assert hasattr(error, "message")
        assert isinstance(error.file, str)
        assert isinstance(error.line, int)
        assert isinstance(error.message, str)


class TestCommandTypeHandling:
    """Test different command types are handled appropriately."""

    def test_pytest_type_recognized(self, pytest_all_pass_output: str) -> None:
        result = mask_output(pytest_all_pass_output, CommandType.PYTEST)
        assert "passed" in result.summary

    def test_mypy_type_recognized(self, mypy_success_output: str) -> None:
        result = mask_output(mypy_success_output, CommandType.MYPY)
        assert "mypy" in result.summary.lower() or "success" in result.summary.lower()

    def test_lint_type_recognized(self, lint_output_with_errors: str) -> None:
        result = mask_output(lint_output_with_errors, CommandType.LINT)
        assert result.summary
        assert len(result.errors) > 0

    def test_generic_type_fallback(self) -> None:
        result = mask_output("some output", CommandType.GENERIC)
        assert result.summary
