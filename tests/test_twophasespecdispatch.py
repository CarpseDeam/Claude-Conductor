"""Tests for TwoPhaseSpecDispatch."""

import warnings
from pathlib import Path
from typing import Literal
from unittest.mock import MagicMock, patch

import pytest

from src.specs.contracts import SpecDocument, SpecTier, ValidationConfig
from src.twophasespecdispatch import (
    PhaseResult,
    SpecExecutionResult,
    TwoPhaseSpecDispatch,
)


@pytest.fixture
def sample_spec() -> SpecDocument:
    """Create a sample spec for testing."""
    return SpecDocument(
        name="TestFeature",
        description="A test feature",
        tier=SpecTier.FEATURE,
        interface=["def foo() -> str"],
        must_do=["Return 'bar'"],
        must_not_do=["Return empty string"],
        edge_cases={"empty input": "raise ValueError"},
        preconditions=["Input must be valid"],
        postconditions=["Output is non-empty"],
        invariants=["State remains consistent"],
        validation=ValidationConfig(
            tests="pytest tests/test_testfeature.py -v",
            typecheck="mypy src/testfeature.py --strict",
        ),
        target_path="src/testfeature.py",
    )


@pytest.fixture
def project_path(tmp_path: Path) -> Path:
    """Create a temporary project directory."""
    return tmp_path


@pytest.fixture
def dispatcher(project_path: Path) -> TwoPhaseSpecDispatch:
    """Create a TwoPhaseSpecDispatch instance."""
    return TwoPhaseSpecDispatch(
        project_path=project_path,
        cli="claude",
        model=None,
    )


class TestPhaseResultDataclass:
    """Tests for PhaseResult data structure."""

    def test_phase_result_has_required_fields(self) -> None:
        """PhaseResult must have phase, success, duration_seconds, files_created, error."""
        result = PhaseResult(
            phase="tests",
            success=True,
            duration_seconds=1.5,
            files_created=["test_file.py"],
            error=None,
        )
        assert result.phase == "tests"
        assert result.success is True
        assert result.duration_seconds == 1.5
        assert result.files_created == ["test_file.py"]
        assert result.error is None

    def test_phase_result_with_error(self) -> None:
        """PhaseResult can contain an error message."""
        result = PhaseResult(
            phase="impl",
            success=False,
            duration_seconds=2.0,
            files_created=[],
            error="CLI crashed",
        )
        assert result.success is False
        assert result.error == "CLI crashed"

    def test_phase_literal_types(self) -> None:
        """Phase must be 'tests' or 'impl'."""
        result_tests = PhaseResult(
            phase="tests",
            success=True,
            duration_seconds=1.0,
            files_created=[],
            error=None,
        )
        result_impl = PhaseResult(
            phase="impl",
            success=True,
            duration_seconds=1.0,
            files_created=[],
            error=None,
        )
        assert result_tests.phase == "tests"
        assert result_impl.phase == "impl"


class TestSpecExecutionResultDataclass:
    """Tests for SpecExecutionResult data structure."""

    def test_spec_execution_result_has_required_fields(self) -> None:
        """SpecExecutionResult must have phase1, phase2, total_duration_seconds, success."""
        phase1 = PhaseResult(
            phase="tests",
            success=True,
            duration_seconds=1.0,
            files_created=["tests/test_foo.py"],
            error=None,
        )
        phase2 = PhaseResult(
            phase="impl",
            success=True,
            duration_seconds=2.0,
            files_created=["src/foo.py"],
            error=None,
        )
        result = SpecExecutionResult(
            phase1=phase1,
            phase2=phase2,
            total_duration_seconds=3.0,
            success=True,
        )
        assert result.phase1 == phase1
        assert result.phase2 == phase2
        assert result.total_duration_seconds == 3.0
        assert result.success is True

    def test_spec_execution_result_phase2_none_when_phase1_fails(self) -> None:
        """Phase2 must be None if phase1 failed."""
        phase1 = PhaseResult(
            phase="tests",
            success=False,
            duration_seconds=1.0,
            files_created=[],
            error="CLI timeout",
        )
        result = SpecExecutionResult(
            phase1=phase1,
            phase2=None,
            total_duration_seconds=1.0,
            success=False,
        )
        assert result.phase2 is None
        assert result.success is False


class TestTwoPhaseSpecDispatchInit:
    """Tests for TwoPhaseSpecDispatch initialization."""

    def test_init_with_required_params(self, project_path: Path) -> None:
        """Constructor accepts project_path, cli, and model."""
        dispatcher = TwoPhaseSpecDispatch(
            project_path=project_path,
            cli="claude",
            model="opus",
        )
        assert dispatcher.project_path == project_path
        assert dispatcher.cli == "claude"
        assert dispatcher.model == "opus"

    def test_init_with_none_model(self, project_path: Path) -> None:
        """Model can be None."""
        dispatcher = TwoPhaseSpecDispatch(
            project_path=project_path,
            cli="gemini",
            model=None,
        )
        assert dispatcher.model is None


class TestBuildPhase1Prompt:
    """Tests for build_phase1_prompt method."""

    def test_phase1_prompt_contains_spec(
        self, dispatcher: TwoPhaseSpecDispatch, sample_spec: SpecDocument
    ) -> None:
        """Phase 1 prompt must include the spec context."""
        prompt = dispatcher.build_phase1_prompt(sample_spec)
        assert sample_spec.name in prompt
        assert sample_spec.description in prompt

    def test_phase1_prompt_forbids_implementation(
        self, dispatcher: TwoPhaseSpecDispatch, sample_spec: SpecDocument
    ) -> None:
        """Phase 1 prompt must explicitly forbid writing implementation code."""
        prompt = dispatcher.build_phase1_prompt(sample_spec)
        # Check for explicit prohibition
        assert "forbid" in prompt.lower() or "must not" in prompt.lower() or "do not" in prompt.lower()
        assert "implementation" in prompt.lower()

    def test_phase1_prompt_includes_anti_exploration(
        self, dispatcher: TwoPhaseSpecDispatch, sample_spec: SpecDocument
    ) -> None:
        """Phase 1 prompt must include anti-exploration directives."""
        prompt = dispatcher.build_phase1_prompt(sample_spec)
        assert "trust the spec" in prompt.lower() or "do not explore" in prompt.lower() or "do not read" in prompt.lower()

    def test_phase1_prompt_includes_circuit_breaker(
        self, dispatcher: TwoPhaseSpecDispatch, sample_spec: SpecDocument
    ) -> None:
        """Phase 1 prompt must include circuit breaker."""
        prompt = dispatcher.build_phase1_prompt(sample_spec)
        assert "circuit breaker" in prompt.lower()


class TestBuildPhase2Prompt:
    """Tests for build_phase2_prompt method."""

    def test_phase2_prompt_contains_spec(
        self, dispatcher: TwoPhaseSpecDispatch, sample_spec: SpecDocument
    ) -> None:
        """Phase 2 prompt must include the spec context."""
        prompt = dispatcher.build_phase2_prompt(sample_spec, "tests/test_foo.py")
        assert sample_spec.name in prompt
        assert sample_spec.description in prompt

    def test_phase2_prompt_forbids_modifying_tests(
        self, dispatcher: TwoPhaseSpecDispatch, sample_spec: SpecDocument
    ) -> None:
        """Phase 2 prompt must explicitly forbid modifying tests."""
        prompt = dispatcher.build_phase2_prompt(sample_spec, "tests/test_foo.py")
        # Check for explicit prohibition of test modification
        assert "do not modify" in prompt.lower() or "must not modify" in prompt.lower() or "forbid" in prompt.lower()
        assert "test" in prompt.lower()

    def test_phase2_prompt_includes_test_path(
        self, dispatcher: TwoPhaseSpecDispatch, sample_spec: SpecDocument
    ) -> None:
        """Phase 2 prompt must include the test file path."""
        test_path = "tests/test_foo.py"
        prompt = dispatcher.build_phase2_prompt(sample_spec, test_path)
        assert test_path in prompt

    def test_phase2_prompt_includes_anti_exploration(
        self, dispatcher: TwoPhaseSpecDispatch, sample_spec: SpecDocument
    ) -> None:
        """Phase 2 prompt must include anti-exploration directives."""
        prompt = dispatcher.build_phase2_prompt(sample_spec, "tests/test_foo.py")
        assert "trust the spec" in prompt.lower() or "do not explore" in prompt.lower() or "do not read" in prompt.lower()

    def test_phase2_prompt_includes_circuit_breaker(
        self, dispatcher: TwoPhaseSpecDispatch, sample_spec: SpecDocument
    ) -> None:
        """Phase 2 prompt must include circuit breaker."""
        prompt = dispatcher.build_phase2_prompt(sample_spec, "tests/test_foo.py")
        assert "circuit breaker" in prompt.lower()


class TestBuildFullPromptDeprecation:
    """Tests for build_full_prompt deprecation."""

    def test_build_full_prompt_raises_deprecation_warning(
        self, dispatcher: TwoPhaseSpecDispatch, sample_spec: SpecDocument
    ) -> None:
        """build_full_prompt must raise DeprecationWarning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            dispatcher.build_full_prompt(sample_spec)
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)

    def test_build_full_prompt_delegates_to_phase1(
        self, dispatcher: TwoPhaseSpecDispatch, sample_spec: SpecDocument
    ) -> None:
        """build_full_prompt must delegate to phase1 prompt after warning."""
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            full_prompt = dispatcher.build_full_prompt(sample_spec)
            phase1_prompt = dispatcher.build_phase1_prompt(sample_spec)
            assert full_prompt == phase1_prompt


class TestRunPhase1:
    """Tests for run_phase1 method."""

    def test_run_phase1_returns_phase_result(
        self, dispatcher: TwoPhaseSpecDispatch, sample_spec: SpecDocument
    ) -> None:
        """run_phase1 must return a PhaseResult."""
        with patch.object(dispatcher, "_execute_cli") as mock_exec:
            mock_exec.return_value = (True, 1.5, ["tests/test_foo.py"], None)
            result = dispatcher.run_phase1(sample_spec)
            assert isinstance(result, PhaseResult)
            assert result.phase == "tests"

    def test_run_phase1_blocks_until_complete(
        self, dispatcher: TwoPhaseSpecDispatch, sample_spec: SpecDocument
    ) -> None:
        """run_phase1 must block until CLI completes."""
        with patch.object(dispatcher, "_execute_cli") as mock_exec:
            mock_exec.return_value = (True, 1.5, ["tests/test_foo.py"], None)
            # If it blocks, it should return a result (not a future/promise)
            result = dispatcher.run_phase1(sample_spec)
            assert result is not None
            mock_exec.assert_called_once()


class TestRunPhase2:
    """Tests for run_phase2 method."""

    def test_run_phase2_returns_phase_result(
        self, dispatcher: TwoPhaseSpecDispatch, sample_spec: SpecDocument
    ) -> None:
        """run_phase2 must return a PhaseResult."""
        with patch.object(dispatcher, "_execute_cli") as mock_exec:
            mock_exec.return_value = (True, 2.0, ["src/foo.py"], None)
            result = dispatcher.run_phase2(sample_spec, "tests/test_foo.py")
            assert isinstance(result, PhaseResult)
            assert result.phase == "impl"

    def test_run_phase2_blocks_until_complete(
        self, dispatcher: TwoPhaseSpecDispatch, sample_spec: SpecDocument
    ) -> None:
        """run_phase2 must block until CLI completes."""
        with patch.object(dispatcher, "_execute_cli") as mock_exec:
            mock_exec.return_value = (True, 2.0, ["src/foo.py"], None)
            result = dispatcher.run_phase2(sample_spec, "tests/test_foo.py")
            assert result is not None
            mock_exec.assert_called_once()


class TestRunSpec:
    """Tests for run_spec orchestration method."""

    def test_run_spec_executes_both_phases_sequentially(
        self, dispatcher: TwoPhaseSpecDispatch, sample_spec: SpecDocument
    ) -> None:
        """run_spec must execute phase1 then phase2 sequentially."""
        call_order: list[str] = []

        def mock_phase1(spec: SpecDocument) -> PhaseResult:
            call_order.append("phase1")
            return PhaseResult(
                phase="tests",
                success=True,
                duration_seconds=1.0,
                files_created=["tests/test_testfeature.py"],
                error=None,
            )

        def mock_phase2(spec: SpecDocument, test_path: str) -> PhaseResult:
            call_order.append("phase2")
            return PhaseResult(
                phase="impl",
                success=True,
                duration_seconds=2.0,
                files_created=["src/testfeature.py"],
                error=None,
            )

        with patch.object(dispatcher, "run_phase1", side_effect=mock_phase1):
            with patch.object(dispatcher, "run_phase2", side_effect=mock_phase2):
                dispatcher.run_spec(sample_spec)
                assert call_order == ["phase1", "phase2"]

    def test_run_spec_returns_spec_execution_result(
        self, dispatcher: TwoPhaseSpecDispatch, sample_spec: SpecDocument
    ) -> None:
        """run_spec must return a SpecExecutionResult."""
        with patch.object(dispatcher, "run_phase1") as mock_p1:
            with patch.object(dispatcher, "run_phase2") as mock_p2:
                mock_p1.return_value = PhaseResult(
                    phase="tests",
                    success=True,
                    duration_seconds=1.0,
                    files_created=["tests/test_testfeature.py"],
                    error=None,
                )
                mock_p2.return_value = PhaseResult(
                    phase="impl",
                    success=True,
                    duration_seconds=2.0,
                    files_created=["src/testfeature.py"],
                    error=None,
                )
                result = dispatcher.run_spec(sample_spec)
                assert isinstance(result, SpecExecutionResult)

    def test_run_spec_skips_phase2_when_phase1_fails(
        self, dispatcher: TwoPhaseSpecDispatch, sample_spec: SpecDocument
    ) -> None:
        """Phase 2 must not start if phase 1 fails."""
        with patch.object(dispatcher, "run_phase1") as mock_p1:
            with patch.object(dispatcher, "run_phase2") as mock_p2:
                mock_p1.return_value = PhaseResult(
                    phase="tests",
                    success=False,
                    duration_seconds=1.0,
                    files_created=[],
                    error="CLI crashed",
                )
                result = dispatcher.run_spec(sample_spec)
                mock_p2.assert_not_called()
                assert result.phase2 is None
                assert result.success is False

    def test_run_spec_calculates_total_duration(
        self, dispatcher: TwoPhaseSpecDispatch, sample_spec: SpecDocument
    ) -> None:
        """Total duration should be sum of both phases."""
        with patch.object(dispatcher, "run_phase1") as mock_p1:
            with patch.object(dispatcher, "run_phase2") as mock_p2:
                mock_p1.return_value = PhaseResult(
                    phase="tests",
                    success=True,
                    duration_seconds=1.5,
                    files_created=["tests/test_testfeature.py"],
                    error=None,
                )
                mock_p2.return_value = PhaseResult(
                    phase="impl",
                    success=True,
                    duration_seconds=2.5,
                    files_created=["src/testfeature.py"],
                    error=None,
                )
                result = dispatcher.run_spec(sample_spec)
                assert result.total_duration_seconds == 4.0


class TestEdgeCases:
    """Tests for edge cases."""

    def test_phase1_fails_with_cli_error(
        self, dispatcher: TwoPhaseSpecDispatch, sample_spec: SpecDocument
    ) -> None:
        """Phase 1 CLI error should report failure, skip phase 2."""
        with patch.object(dispatcher, "_execute_cli") as mock_exec:
            mock_exec.return_value = (False, 1.0, [], "CLI error: timeout")
            result = dispatcher.run_spec(sample_spec)
            assert result.phase1.success is False
            assert result.phase1.error == "CLI error: timeout"
            assert result.phase2 is None

    def test_phase1_no_test_file_generated(
        self, dispatcher: TwoPhaseSpecDispatch, sample_spec: SpecDocument
    ) -> None:
        """Phase 1 produces no test file should fail with clear error."""
        with patch.object(dispatcher, "_execute_cli") as mock_exec:
            # CLI succeeds but no test file created
            mock_exec.return_value = (True, 1.0, [], None)
            result = dispatcher.run_spec(sample_spec)
            assert result.phase1.success is False
            assert "no tests generated" in result.phase1.error.lower()

    def test_test_path_already_exists_warns_but_proceeds(
        self, dispatcher: TwoPhaseSpecDispatch, sample_spec: SpecDocument, project_path: Path
    ) -> None:
        """Test path already exists should warn but proceed."""
        # Create existing test file
        test_dir = project_path / "tests"
        test_dir.mkdir(parents=True, exist_ok=True)
        existing_test = test_dir / "test_testfeature.py"
        existing_test.write_text("# existing test")

        with patch.object(dispatcher, "_execute_cli") as mock_exec:
            mock_exec.return_value = (True, 1.0, ["tests/test_testfeature.py"], None)
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                result = dispatcher.run_phase1(sample_spec)
                # Should have a warning about existing file
                warning_messages = [str(warning.message) for warning in w]
                assert any("exist" in msg.lower() for msg in warning_messages)
                # But should still proceed
                assert result is not None


class TestInvariants:
    """Tests for invariants."""

    def test_phase2_never_runs_before_phase1(
        self, dispatcher: TwoPhaseSpecDispatch, sample_spec: SpecDocument
    ) -> None:
        """Invariant: Phase 2 never runs before phase 1 completes."""
        execution_times: list[tuple[str, float]] = []
        import time

        def mock_phase1(spec: SpecDocument) -> PhaseResult:
            start = time.time()
            time.sleep(0.01)  # Simulate work
            execution_times.append(("phase1_complete", time.time()))
            return PhaseResult(
                phase="tests",
                success=True,
                duration_seconds=0.01,
                files_created=["tests/test_testfeature.py"],
                error=None,
            )

        def mock_phase2(spec: SpecDocument, test_path: str) -> PhaseResult:
            execution_times.append(("phase2_start", time.time()))
            return PhaseResult(
                phase="impl",
                success=True,
                duration_seconds=0.01,
                files_created=["src/testfeature.py"],
                error=None,
            )

        with patch.object(dispatcher, "run_phase1", side_effect=mock_phase1):
            with patch.object(dispatcher, "run_phase2", side_effect=mock_phase2):
                dispatcher.run_spec(sample_spec)
                # Verify phase2 started after phase1 completed
                phase1_complete_time = next(t for name, t in execution_times if name == "phase1_complete")
                phase2_start_time = next(t for name, t in execution_times if name == "phase2_start")
                assert phase2_start_time >= phase1_complete_time

    def test_each_phase_has_isolated_context(
        self, dispatcher: TwoPhaseSpecDispatch, sample_spec: SpecDocument
    ) -> None:
        """Invariant: Each phase has isolated context (fresh CLI invocation)."""
        cli_invocations: list[str] = []

        def mock_execute(prompt: str, phase: str) -> tuple[bool, float, list[str], str | None]:
            cli_invocations.append(phase)
            if phase == "tests":
                return (True, 1.0, ["tests/test_testfeature.py"], None)
            return (True, 1.0, ["src/testfeature.py"], None)

        with patch.object(dispatcher, "_execute_cli", side_effect=mock_execute):
            dispatcher.run_spec(sample_spec)
            # Two separate CLI invocations
            assert len(cli_invocations) == 2

    def test_spec_document_immutable_during_execution(
        self, dispatcher: TwoPhaseSpecDispatch, sample_spec: SpecDocument
    ) -> None:
        """Invariant: Original spec document is immutable throughout execution."""
        original_name = sample_spec.name
        original_description = sample_spec.description

        with patch.object(dispatcher, "run_phase1") as mock_p1:
            with patch.object(dispatcher, "run_phase2") as mock_p2:
                mock_p1.return_value = PhaseResult(
                    phase="tests",
                    success=True,
                    duration_seconds=1.0,
                    files_created=["tests/test_testfeature.py"],
                    error=None,
                )
                mock_p2.return_value = PhaseResult(
                    phase="impl",
                    success=True,
                    duration_seconds=2.0,
                    files_created=["src/testfeature.py"],
                    error=None,
                )
                dispatcher.run_spec(sample_spec)

        # Spec should be unchanged
        assert sample_spec.name == original_name
        assert sample_spec.description == original_description


class TestMustNotDoConstraints:
    """Tests for Must Not Do constraints."""

    def test_phase2_does_not_receive_phase1_context(
        self, dispatcher: TwoPhaseSpecDispatch, sample_spec: SpecDocument
    ) -> None:
        """Must not pass phase 1's conversation context to phase 2."""
        phase1_prompt = dispatcher.build_phase1_prompt(sample_spec)
        phase2_prompt = dispatcher.build_phase2_prompt(sample_spec, "tests/test_foo.py")

        # Phase 2 prompt should not contain any phase 1 specific content markers
        # that would indicate context bleeding
        assert "PHASE 1" not in phase2_prompt or "test generation" not in phase2_prompt.lower()

    def test_phases_not_run_in_parallel(
        self, dispatcher: TwoPhaseSpecDispatch, sample_spec: SpecDocument
    ) -> None:
        """Must not run phases in parallel."""
        import threading

        concurrent_executions = {"count": 0, "max": 0}
        lock = threading.Lock()

        original_run_phase1 = dispatcher.run_phase1
        original_run_phase2 = dispatcher.run_phase2

        def mock_phase1(spec: SpecDocument) -> PhaseResult:
            with lock:
                concurrent_executions["count"] += 1
                concurrent_executions["max"] = max(
                    concurrent_executions["max"], concurrent_executions["count"]
                )
            import time
            time.sleep(0.01)
            with lock:
                concurrent_executions["count"] -= 1
            return PhaseResult(
                phase="tests",
                success=True,
                duration_seconds=0.01,
                files_created=["tests/test_testfeature.py"],
                error=None,
            )

        def mock_phase2(spec: SpecDocument, test_path: str) -> PhaseResult:
            with lock:
                concurrent_executions["count"] += 1
                concurrent_executions["max"] = max(
                    concurrent_executions["max"], concurrent_executions["count"]
                )
            import time
            time.sleep(0.01)
            with lock:
                concurrent_executions["count"] -= 1
            return PhaseResult(
                phase="impl",
                success=True,
                duration_seconds=0.01,
                files_created=["src/testfeature.py"],
                error=None,
            )

        with patch.object(dispatcher, "run_phase1", side_effect=mock_phase1):
            with patch.object(dispatcher, "run_phase2", side_effect=mock_phase2):
                dispatcher.run_spec(sample_spec)
                # Max concurrent should be 1
                assert concurrent_executions["max"] == 1
