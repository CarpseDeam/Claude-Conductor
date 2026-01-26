"""Tests for single-phase spec execution refactor."""

from pathlib import Path

import pytest

from src.specs.contracts import PhaseRequest, SpecDocument, SpecTier, ValidationConfig
from src.specs.prompts import SpecPromptBuilder
from src.specs.runner import SpecPhaseRunner


@pytest.fixture
def sample_spec() -> SpecDocument:
    """Create a sample spec document for testing."""
    return SpecDocument(
        name="TestFeature",
        description="A test feature for validation.",
        tier=SpecTier.FEATURE,
        interface=["do_something(x: int) -> str"],
        must_do=["Process input correctly", "Return formatted output"],
        must_not_do=["Modify global state", "Raise unhandled exceptions"],
        edge_cases={"Empty input": "Return empty string"},
        preconditions=["Input must be non-negative"],
        postconditions=["Output is valid string"],
        invariants=[],
        validation=ValidationConfig(tests="pytest tests/ -v"),
        target_path="src/test_feature.py",
    )


@pytest.fixture
def spec_with_empty_edge_cases() -> SpecDocument:
    """Create a spec with empty edge cases section."""
    return SpecDocument(
        name="NoEdgeCases",
        description="A feature with no edge cases.",
        tier=SpecTier.FEATURE,
        interface=["simple_func() -> bool"],
        must_do=["Return True"],
        must_not_do=[],
        edge_cases={},
        preconditions=[],
        postconditions=[],
        invariants=[],
        validation=ValidationConfig(tests="pytest tests/ -v"),
        target_path="src/no_edge_cases.py",
    )


@pytest.fixture
def runner(sample_spec: SpecDocument, tmp_path: Path) -> SpecPhaseRunner:
    """Create a SpecPhaseRunner instance."""
    return SpecPhaseRunner(sample_spec, tmp_path)


@pytest.fixture
def prompt_builder() -> SpecPromptBuilder:
    """Create a SpecPromptBuilder instance."""
    return SpecPromptBuilder()


class TestSingleCLIInvocation:
    """Tests for Must Do: Single CLI invocation per spec."""

    def test_get_request_returns_phase_request(
        self, runner: SpecPhaseRunner
    ) -> None:
        """get_request returns a PhaseRequest for unified execution."""
        request = runner.get_request()
        assert isinstance(request, PhaseRequest)

    def test_get_request_contains_spec(
        self, runner: SpecPhaseRunner, sample_spec: SpecDocument
    ) -> None:
        """get_request includes the spec document."""
        request = runner.get_request()
        assert request.spec == sample_spec

    def test_get_request_contains_unified_prompt(
        self, runner: SpecPhaseRunner
    ) -> None:
        """get_request contains prompt for both implementation and tests."""
        request = runner.get_request()
        assert "implement" in request.prompt.lower()
        assert "test" in request.prompt.lower()


class TestUnifiedPrompt:
    """Tests for Must Do: Prompt instructs agent to implement and write tests."""

    def test_build_prompt_returns_string(
        self, prompt_builder: SpecPromptBuilder, sample_spec: SpecDocument
    ) -> None:
        """build_prompt returns a string prompt."""
        prompt = prompt_builder.build_prompt(sample_spec)
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_prompt_instructs_implementation_first(
        self, prompt_builder: SpecPromptBuilder, sample_spec: SpecDocument
    ) -> None:
        """Prompt instructs to implement the interface first."""
        prompt = prompt_builder.build_prompt(sample_spec)
        impl_pos = prompt.lower().find("implement")
        test_pos = prompt.lower().find("write tests")
        assert impl_pos != -1, "Prompt must mention implementing"
        assert test_pos != -1, "Prompt must mention writing tests"
        assert impl_pos < test_pos, "Implementation must come before tests"

    def test_prompt_includes_must_do_test_instruction(
        self, prompt_builder: SpecPromptBuilder, sample_spec: SpecDocument
    ) -> None:
        """Prompt instructs to write tests for each Must Do item."""
        prompt = prompt_builder.build_prompt(sample_spec)
        assert "must do" in prompt.lower() or "must_do" in prompt.lower()

    def test_prompt_includes_edge_case_test_instruction(
        self, prompt_builder: SpecPromptBuilder, sample_spec: SpecDocument
    ) -> None:
        """Prompt instructs to write tests for each edge case."""
        prompt = prompt_builder.build_prompt(sample_spec)
        assert "edge case" in prompt.lower() or "edge_case" in prompt.lower()


class TestContractBehaviorTesting:
    """Tests for Must Do: Tests validate contract/behavior, not implementation."""

    def test_prompt_emphasizes_behavior_testing(
        self, prompt_builder: SpecPromptBuilder, sample_spec: SpecDocument
    ) -> None:
        """Prompt emphasizes testing behavior/contract, not implementation details."""
        prompt = prompt_builder.build_prompt(sample_spec)
        assert "behavior" in prompt.lower() or "contract" in prompt.lower()


class TestPhaseTrackingRemoval:
    """Tests for Must Do: Remove all phase tracking state from SpecPhaseRunner."""

    def test_runner_has_no_current_phase_attribute(
        self, runner: SpecPhaseRunner
    ) -> None:
        """SpecPhaseRunner should not have current_phase attribute."""
        assert not hasattr(runner, "current_phase")

    def test_runner_has_no_test_path_tracking(
        self, runner: SpecPhaseRunner
    ) -> None:
        """SpecPhaseRunner should not track test_path for phase transitions."""
        # If test_path exists, it should not be used for phase tracking
        if hasattr(runner, "test_path"):
            # Call get_request - should work without test_path being set
            request = runner.get_request()
            assert request is not None


class TestMethodRemoval:
    """Tests for Must Do: Remove deprecated methods."""

    def test_infer_test_path_removed_from_runner(
        self, runner: SpecPhaseRunner
    ) -> None:
        """infer_test_path should be removed from SpecPhaseRunner."""
        assert not hasattr(runner, "infer_test_path")

    def test_get_phase2_request_removed(
        self, runner: SpecPhaseRunner
    ) -> None:
        """get_phase2_request should be removed."""
        assert not hasattr(runner, "get_phase2_request")

    def test_complete_phase1_removed(
        self, runner: SpecPhaseRunner
    ) -> None:
        """complete_phase1 should be removed."""
        assert not hasattr(runner, "complete_phase1")

    def test_get_phase1_request_removed(
        self, runner: SpecPhaseRunner
    ) -> None:
        """get_phase1_request should be removed (replaced by get_request)."""
        assert not hasattr(runner, "get_phase1_request")

    def test_build_phase1_prompt_removed(
        self, prompt_builder: SpecPromptBuilder
    ) -> None:
        """build_phase1_prompt should be removed (replaced by build_prompt)."""
        assert not hasattr(prompt_builder, "build_phase1_prompt")

    def test_build_phase2_prompt_removed(
        self, prompt_builder: SpecPromptBuilder
    ) -> None:
        """build_phase2_prompt should be removed (replaced by build_prompt)."""
        assert not hasattr(prompt_builder, "build_phase2_prompt")


class TestCompleteMethod:
    """Tests for new complete() method."""

    def test_complete_method_exists(
        self, runner: SpecPhaseRunner
    ) -> None:
        """complete() method should exist on SpecPhaseRunner."""
        assert hasattr(runner, "complete")
        assert callable(runner.complete)

    def test_complete_accepts_success_bool(
        self, runner: SpecPhaseRunner
    ) -> None:
        """complete() accepts a success boolean parameter."""
        # Should not raise
        runner.complete(success=True)
        runner.complete(success=False)

    def test_complete_returns_none(
        self, runner: SpecPhaseRunner
    ) -> None:
        """complete() returns None."""
        result = runner.complete(success=True)
        assert result is None


class TestEdgeCaseEmptyEdgeCases:
    """Tests for Edge Case: Spec with empty edge cases section."""

    def test_prompt_generated_with_empty_edge_cases(
        self, prompt_builder: SpecPromptBuilder,
        spec_with_empty_edge_cases: SpecDocument
    ) -> None:
        """Prompt is generated even when edge_cases is empty."""
        prompt = prompt_builder.build_prompt(spec_with_empty_edge_cases)
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_must_do_tests_still_instructed_with_empty_edge_cases(
        self, prompt_builder: SpecPromptBuilder,
        spec_with_empty_edge_cases: SpecDocument
    ) -> None:
        """Must Do tests are still instructed even with empty edge cases."""
        prompt = prompt_builder.build_prompt(spec_with_empty_edge_cases)
        assert "must do" in prompt.lower() or "must_do" in prompt.lower()


class TestMustNotDoConstraints:
    """Tests for Must Not Do constraints."""

    def test_does_not_generate_tests_before_implementation(
        self, prompt_builder: SpecPromptBuilder, sample_spec: SpecDocument
    ) -> None:
        """Prompt does not instruct generating tests before implementation."""
        prompt = prompt_builder.build_prompt(sample_spec)
        # Implementation should be mentioned before test writing
        impl_pos = prompt.lower().find("implement")
        test_gen_phrases = ["generate tests", "write tests", "create tests"]
        test_positions = [
            prompt.lower().find(phrase)
            for phrase in test_gen_phrases
            if prompt.lower().find(phrase) != -1
        ]
        if test_positions:
            first_test_pos = min(test_positions)
            assert impl_pos < first_test_pos, (
                "Should not instruct test generation before implementation"
            )

    def test_does_not_invent_test_cases_beyond_spec(
        self, prompt_builder: SpecPromptBuilder, sample_spec: SpecDocument
    ) -> None:
        """Prompt does not encourage inventing tests beyond spec definition."""
        prompt = prompt_builder.build_prompt(sample_spec)
        # Should not contain phrases encouraging additional tests
        forbidden_phrases = [
            "additional tests",
            "extra tests",
            "more tests than",
            "beyond the spec",
        ]
        prompt_lower = prompt.lower()
        for phrase in forbidden_phrases:
            assert phrase not in prompt_lower, (
                f"Prompt should not encourage '{phrase}'"
            )


class TestProseModePersistence:
    """Tests for Must Not Do: Do not break prose mode dispatch flow."""

    def test_runner_only_handles_spec_documents(
        self, tmp_path: Path
    ) -> None:
        """Runner is constructed with SpecDocument, not arbitrary input."""
        # This ensures the runner is spec-specific and doesn't interfere with prose mode
        with pytest.raises(TypeError):
            SpecPhaseRunner(None, tmp_path)  # type: ignore[arg-type]


class TestTaskTrackerUnmodified:
    """Tests for Must Not Do: Do not modify TaskTracker or task contracts."""

    def test_phase_request_structure_unchanged(
        self, runner: SpecPhaseRunner
    ) -> None:
        """PhaseRequest structure remains compatible with existing contracts."""
        request = runner.get_request()
        # PhaseRequest should have expected fields
        assert hasattr(request, "phase")
        assert hasattr(request, "prompt")
        assert hasattr(request, "spec")
