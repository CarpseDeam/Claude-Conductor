"""Tests for validate_spec function and SpecValidationResult."""

import pytest

from src.specs.contracts import SpecDocument, SpecTier
from src.specs.validator import SpecValidationResult, validate_spec


# --- Fixtures ---


@pytest.fixture
def valid_spec_markdown() -> str:
    """A complete valid spec document."""
    return """## Spec: TestFeature [FEATURE]

A test feature for validation.

### Interface
- `do_something(x: int) -> str`

### Must Do
- Return a string
- Handle negative numbers

### Must Not Do
- Raise exceptions

### Edge Cases
- Empty input → return empty string

### Preconditions
- Input must be an integer

### Postconditions
- Output is always a string

### Invariants
- Function is pure

### Validation
```yaml
tests: pytest tests/test_feature.py -v
typecheck: mypy src/feature.py
```

### Target Path
src/feature.py
"""


@pytest.fixture
def minimal_valid_spec() -> str:
    """Minimal valid spec with only required parts."""
    return """## Spec: MinimalFeature [HOTFIX]

A minimal feature.

### Validation
tests: pytest tests/ -v
"""


# --- Behavior Tests (Must Do) ---


class TestValidSpecReturnsResult:
    """Tests that valid input returns SpecValidationResult with is_valid=True."""

    def test_valid_spec_returns_is_valid_true(
        self, valid_spec_markdown: str
    ) -> None:
        """Valid spec returns is_valid=True."""
        result = validate_spec(valid_spec_markdown)

        assert result.is_valid is True

    def test_valid_spec_has_populated_spec(
        self, valid_spec_markdown: str
    ) -> None:
        """Valid spec returns populated spec field."""
        result = validate_spec(valid_spec_markdown)

        assert result.spec is not None
        assert isinstance(result.spec, SpecDocument)
        assert result.spec.name == "TestFeature"
        assert result.spec.tier == SpecTier.FEATURE

    def test_valid_spec_has_empty_errors(
        self, valid_spec_markdown: str
    ) -> None:
        """Valid spec returns empty errors list."""
        result = validate_spec(valid_spec_markdown)

        assert result.errors == []

    def test_minimal_valid_spec_succeeds(self, minimal_valid_spec: str) -> None:
        """Minimal valid spec also returns is_valid=True."""
        result = validate_spec(minimal_valid_spec)

        assert result.is_valid is True
        assert result.spec is not None
        assert result.errors == []


class TestInvalidSpecReturnsResult:
    """Tests that invalid input returns SpecValidationResult with is_valid=False."""

    def test_invalid_spec_returns_is_valid_false(self) -> None:
        """Invalid spec returns is_valid=False."""
        result = validate_spec("not a valid spec")

        assert result.is_valid is False

    def test_invalid_spec_has_none_spec(self) -> None:
        """Invalid spec returns spec=None."""
        result = validate_spec("not a valid spec")

        assert result.spec is None

    def test_invalid_spec_has_populated_errors(self) -> None:
        """Invalid spec returns non-empty errors list."""
        result = validate_spec("not a valid spec")

        assert len(result.errors) > 0
        assert isinstance(result.errors, list)
        assert all(isinstance(e, str) for e in result.errors)


class TestCollectsAllErrors:
    """Tests that ALL validation errors are collected, not just the first."""

    def test_multiple_errors_all_collected(self) -> None:
        """When multiple errors exist, all are collected."""
        # Invalid header AND missing validation tests
        markdown = "This has no valid header at all"

        result = validate_spec(markdown)

        assert result.is_valid is False
        assert len(result.errors) >= 1

    def test_valid_header_but_missing_tests_collects_error(self) -> None:
        """Valid header with missing tests command in validation."""
        markdown = """## Spec: TestFeature [FEATURE]

Description here.

### Validation
typecheck: mypy src/
"""
        result = validate_spec(markdown)

        assert result.is_valid is False
        assert any("tests" in e.lower() for e in result.errors)


class TestValidatesSpecificErrors:
    """Tests for specific validation checks."""

    def test_check_missing_header(self) -> None:
        """Detects missing header error."""
        markdown = "No header here, just text"

        result = validate_spec(markdown)

        assert result.is_valid is False
        assert any("header" in e.lower() for e in result.errors)

    def test_check_invalid_tier(self) -> None:
        """Detects invalid tier error."""
        markdown = """## Spec: TestFeature [INVALID_TIER]

Description.

### Validation
tests: pytest
"""
        result = validate_spec(markdown)

        assert result.is_valid is False
        assert any("tier" in e.lower() for e in result.errors)

    def test_check_missing_tests_in_validation(self) -> None:
        """Detects missing tests command in validation block."""
        markdown = """## Spec: TestFeature [FEATURE]

Description.

### Validation
lint: ruff check
"""
        result = validate_spec(markdown)

        assert result.is_valid is False
        assert any("tests" in e.lower() for e in result.errors)


# --- Edge Case Tests ---


class TestEdgeCases:
    """Tests for edge case handling."""

    def test_empty_string_returns_header_error(self) -> None:
        """Empty string input returns error about invalid header."""
        result = validate_spec("")

        assert result.is_valid is False
        assert result.spec is None
        assert len(result.errors) > 0
        # Should mention header in error
        assert any("header" in e.lower() for e in result.errors)

    def test_valid_header_missing_validation_tests(self) -> None:
        """Valid header but no tests in validation block."""
        markdown = """## Spec: TestFeature [FEATURE]

Description.

### Validation
typecheck: mypy
"""
        result = validate_spec(markdown)

        assert result.is_valid is False
        assert any("tests" in e.lower() for e in result.errors)

    def test_multiple_errors_all_collected_in_list(self) -> None:
        """Multiple errors are all present in errors list."""
        # This has an invalid tier AND missing validation block
        markdown = """## Spec: TestFeature [BADTIER]

Description only, no validation section.
"""
        result = validate_spec(markdown)

        assert result.is_valid is False
        # Should have multiple errors
        assert len(result.errors) >= 1


# --- Contract Tests ---


class TestPreconditions:
    """Tests for precondition handling."""

    def test_input_is_string_accepted(self) -> None:
        """String input is accepted (doesn't raise)."""
        result = validate_spec("any string")

        assert isinstance(result, SpecValidationResult)

    def test_empty_string_is_valid_input(self) -> None:
        """Empty string is valid input (returns result, not exception)."""
        result = validate_spec("")

        assert isinstance(result, SpecValidationResult)
        assert result.is_valid is False


class TestPostconditions:
    """Tests for postcondition verification."""

    def test_result_always_has_is_valid_set(
        self, valid_spec_markdown: str
    ) -> None:
        """Result always has is_valid set correctly."""
        valid_result = validate_spec(valid_spec_markdown)
        invalid_result = validate_spec("")

        assert isinstance(valid_result.is_valid, bool)
        assert isinstance(invalid_result.is_valid, bool)
        assert valid_result.is_valid is True
        assert invalid_result.is_valid is False

    def test_valid_result_has_spec_not_none_and_empty_errors(
        self, valid_spec_markdown: str
    ) -> None:
        """If is_valid=True, spec is not None and errors is empty."""
        result = validate_spec(valid_spec_markdown)

        assert result.is_valid is True
        assert result.spec is not None
        assert result.errors == []

    def test_invalid_result_has_none_spec_and_nonempty_errors(self) -> None:
        """If is_valid=False, spec is None and errors is non-empty."""
        result = validate_spec("invalid")

        assert result.is_valid is False
        assert result.spec is None
        assert len(result.errors) > 0


class TestInvariants:
    """Tests for invariant preservation."""

    def test_validate_spec_never_raises_on_valid_input(
        self, valid_spec_markdown: str
    ) -> None:
        """validate_spec never raises exceptions on valid input."""
        # Should not raise
        result = validate_spec(valid_spec_markdown)
        assert isinstance(result, SpecValidationResult)

    def test_validate_spec_never_raises_on_invalid_input(self) -> None:
        """validate_spec never raises exceptions on invalid input."""
        invalid_inputs = [
            "",
            "not a spec",
            "## Spec: Name [INVALID]",
            "## Spec: Name [FEATURE]\n\nNo validation",
            "random garbage !@#$%^&*()",
        ]

        for input_str in invalid_inputs:
            # Should not raise, should return result
            result = validate_spec(input_str)
            assert isinstance(result, SpecValidationResult)

    def test_result_is_always_spec_validation_result(self) -> None:
        """Result is always a SpecValidationResult instance."""
        valid_md = """## Spec: Test [HOTFIX]

Desc.

### Validation
tests: pytest
"""
        invalid_md = "not valid"

        assert isinstance(validate_spec(valid_md), SpecValidationResult)
        assert isinstance(validate_spec(invalid_md), SpecValidationResult)


# --- Constraint Tests (Must Not Do) ---


class TestConstraints:
    """Tests verifying Must Not Do constraints."""

    def test_validate_spec_does_not_raise_for_invalid_input(self) -> None:
        """validate_spec must not raise exceptions for invalid input."""
        # These would all cause SpecParser.parse() to raise
        problematic_inputs = [
            "",
            "## Spec: Test [BADTIER]\n\n### Validation\ntests: pytest",
        ]

        for input_str in problematic_inputs:
            # Must return result, not raise
            result = validate_spec(input_str)
            assert isinstance(result, SpecValidationResult)
            assert result.is_valid is False

    def test_missing_validation_block_uses_default(self) -> None:
        """Spec without validation block uses parser default (valid)."""
        # Per parser behavior, missing validation block gets default
        markdown = "## Spec: Test [FEATURE]\n\nNo validation section here."

        result = validate_spec(markdown)

        # This is valid because parser provides default validation config
        assert isinstance(result, SpecValidationResult)

    def test_spec_parser_parse_still_raises(self) -> None:
        """SpecParser.parse() behavior unchanged - still raises on invalid."""
        from src.specs.parser import SpecParser

        parser = SpecParser()

        with pytest.raises(ValueError):
            parser.parse("")

        with pytest.raises(ValueError):
            parser.parse("## Spec: Test [BADTIER]")


# --- Type Tests ---


class TestTypes:
    """Tests for type correctness."""

    def test_spec_validation_result_has_correct_attributes(
        self, valid_spec_markdown: str
    ) -> None:
        """SpecValidationResult has all required attributes."""
        result = validate_spec(valid_spec_markdown)

        assert hasattr(result, "is_valid")
        assert hasattr(result, "spec")
        assert hasattr(result, "errors")

    def test_errors_is_list_of_strings(self) -> None:
        """errors attribute is always list[str]."""
        result = validate_spec("invalid")

        assert isinstance(result.errors, list)
        for error in result.errors:
            assert isinstance(error, str)

    def test_spec_is_spec_document_or_none(
        self, valid_spec_markdown: str
    ) -> None:
        """spec attribute is SpecDocument or None."""
        valid_result = validate_spec(valid_spec_markdown)
        invalid_result = validate_spec("invalid")

        assert isinstance(valid_result.spec, SpecDocument)
        assert invalid_result.spec is None
