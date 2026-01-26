"""Two-phase spec execution with separate test generation and implementation."""

from __future__ import annotations

import subprocess
import time
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from src.specs.contracts import SpecDocument


@dataclass
class PhaseResult:
    """Result of a single phase execution."""

    phase: Literal["tests", "impl"]
    success: bool
    duration_seconds: float
    files_created: list[str]
    error: str | None


@dataclass
class SpecExecutionResult:
    """Result of complete spec execution (both phases)."""

    phase1: PhaseResult
    phase2: PhaseResult | None
    total_duration_seconds: float
    success: bool


class TwoPhaseSpecDispatch:
    """Two-phase spec execution separating test generation from implementation.

    Phase 1 generates tests in fresh context.
    Phase 2 implements against those tests in fresh context.
    This prevents bias from seeing tests while implementing.
    """

    def __init__(
        self,
        project_path: Path,
        cli: str,
        model: str | None,
    ) -> None:
        """Initialize the dispatcher.

        Args:
            project_path: Path to the project directory.
            cli: CLI tool to use (claude, gemini, codex).
            model: Optional model to use, or None for default.
        """
        self.project_path = project_path
        self.cli = cli
        self.model = model

    def build_phase1_prompt(self, spec: SpecDocument) -> str:
        """Build prompt for test generation only.

        Args:
            spec: The specification document.

        Returns:
            Prompt string that instructs CLI to generate tests only.
        """
        test_path = self._infer_test_path(spec)
        sections = [
            "# Phase 1: Test Generation",
            "",
            "## CRITICAL: TRUST THE SPEC",
            "",
            "The specification below is COMPLETE. Do not:",
            "- Read README, ARCHITECTURE, or documentation files",
            "- Search for patterns or conventions in the codebase",
            "- Explore directory structures",
            "- Read files unrelated to test generation",
            "",
            "Only read files that:",
            "1. You need to import from (check the target path's neighbors)",
            "2. Contain types/classes referenced in the interface",
            "",
            "The spec tells you exactly what to test. Trust it.",
            "",
            "## CIRCUIT BREAKER",
            "",
            "If you have made 8+ file reads without writing any code, STOP.",
            "You are exploring instead of implementing. The spec is complete.",
            "Write the tests now with what you know.",
            "",
            "## CRITICAL CONSTRAINT: DO NOT WRITE IMPLEMENTATION CODE",
            "",
            "You are FORBIDDEN from writing implementation code in this phase.",
            "Your ONLY task is to generate the test file.",
            "Do not create the implementation file.",
            "Do not write any production code.",
            "Only write tests.",
            "",
            "## THE SPECIFICATION",
            "",
            spec.to_prompt_context(),
            "",
            "## YOUR TASK",
            "",
            f"Create a pytest test suite at: `{test_path}`",
            "",
            "Test Generation Rules:",
            "1. Create one test per 'Must Do' requirement",
            "2. Create one test per edge case",
            "3. Create tests for precondition violations",
            "4. Create tests for postcondition verification",
            "5. Create tests verifying 'Must Not Do' constraints",
            "",
            "Write tests that will FAIL until implementation exists.",
            "Do NOT write any implementation code.",
        ]
        return "\n".join(sections)

    def build_phase2_prompt(self, spec: SpecDocument, test_path: str) -> str:
        """Build prompt for implementation against existing tests.

        Args:
            spec: The specification document.
            test_path: Path to the test file generated in phase 1.

        Returns:
            Prompt string that instructs CLI to implement against tests.
        """
        impl_path = self._infer_impl_path(spec)
        sections = [
            "# Phase 2: Implementation",
            "",
            "## CRITICAL: TRUST THE SPEC",
            "",
            "The specification below is COMPLETE. Do not:",
            "- Read README, ARCHITECTURE, or documentation files",
            "- Search for patterns or conventions in the codebase",
            "- Explore directory structures",
            "- Read files unrelated to your implementation",
            "",
            "Only read files that:",
            "1. You need to import from (check the target path's neighbors)",
            "2. Contain types/classes referenced in the interface",
            "3. The test file at the specified path",
            "",
            "The spec tells you exactly what to build. Trust it.",
            "",
            "## CIRCUIT BREAKER",
            "",
            "If you have made 8+ file reads without writing any code, STOP.",
            "You are exploring instead of implementing. The spec is complete.",
            "Write the implementation now with what you know.",
            "",
            "## CRITICAL CONSTRAINT: DO NOT MODIFY TESTS",
            "",
            "You are FORBIDDEN from modifying the test file.",
            "The tests at the path below are fixed and immutable.",
            "Your task is to make them pass, not to change them.",
            "Do not edit, delete, or modify any test code.",
            "",
            f"## TEST FILE LOCATION: `{test_path}`",
            "",
            "Read this file to understand what you must implement.",
            "Then implement the code to make all tests pass.",
            "",
            "## THE SPECIFICATION",
            "",
            spec.to_prompt_context(),
            "",
            "## YOUR TASK",
            "",
            f"Implement the specification at: `{impl_path}`",
            "",
            "Implementation Rules:",
            "1. Follow interface signatures EXACTLY",
            "2. Implement minimal code to pass all tests",
            "3. Handle all edge cases as specified",
            "4. Ensure preconditions are checked",
            "5. Ensure postconditions are satisfied",
            "",
            "Run the tests and iterate until all pass.",
            f"Test command: {spec.validation.tests}",
        ]
        return "\n".join(sections)

    def build_full_prompt(self, spec: SpecDocument) -> str:
        """DEPRECATED: Use build_phase1_prompt and build_phase2_prompt instead.

        Args:
            spec: The specification document.

        Returns:
            Phase 1 prompt (after raising deprecation warning).
        """
        warnings.warn(
            "build_full_prompt is deprecated. Use build_phase1_prompt and "
            "build_phase2_prompt for two-phase execution.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.build_phase1_prompt(spec)

    def run_phase1(self, spec: SpecDocument) -> PhaseResult:
        """Run phase 1: test generation.

        Args:
            spec: The specification document.

        Returns:
            PhaseResult with outcome of test generation.
        """
        test_path = self._infer_test_path(spec)
        full_test_path = self.project_path / test_path

        # Warn if test file already exists
        if full_test_path.exists():
            warnings.warn(
                f"Test file already exists at {test_path}. Proceeding anyway.",
                UserWarning,
                stacklevel=2,
            )

        prompt = self.build_phase1_prompt(spec)
        success, duration, files_created, error = self._execute_cli(prompt, "tests")

        # Verify test file was created
        if success and test_path not in files_created:
            # Check if file exists on disk
            if not full_test_path.exists():
                return PhaseResult(
                    phase="tests",
                    success=False,
                    duration_seconds=duration,
                    files_created=files_created,
                    error=f"No tests generated at expected path: {test_path}",
                )

        return PhaseResult(
            phase="tests",
            success=success,
            duration_seconds=duration,
            files_created=files_created,
            error=error,
        )

    def run_phase2(self, spec: SpecDocument, test_path: str) -> PhaseResult:
        """Run phase 2: implementation against existing tests.

        Args:
            spec: The specification document.
            test_path: Path to test file from phase 1.

        Returns:
            PhaseResult with outcome of implementation.
        """
        prompt = self.build_phase2_prompt(spec, test_path)
        success, duration, files_created, error = self._execute_cli(prompt, "impl")

        return PhaseResult(
            phase="impl",
            success=success,
            duration_seconds=duration,
            files_created=files_created,
            error=error,
        )

    def run_spec(self, spec: SpecDocument) -> SpecExecutionResult:
        """Orchestrate both phases sequentially.

        Args:
            spec: The specification document.

        Returns:
            SpecExecutionResult with outcomes of both phases.
        """
        # Phase 1: Generate tests
        phase1_result = self.run_phase1(spec)

        if not phase1_result.success:
            return SpecExecutionResult(
                phase1=phase1_result,
                phase2=None,
                total_duration_seconds=phase1_result.duration_seconds,
                success=False,
            )

        # Determine test path from phase 1
        test_path = self._infer_test_path(spec)

        # Phase 2: Implement against tests
        phase2_result = self.run_phase2(spec, test_path)

        total_duration = phase1_result.duration_seconds + phase2_result.duration_seconds

        return SpecExecutionResult(
            phase1=phase1_result,
            phase2=phase2_result,
            total_duration_seconds=total_duration,
            success=phase2_result.success,
        )

    def _execute_cli(
        self, prompt: str, phase: str
    ) -> tuple[bool, float, list[str], str | None]:
        """Execute CLI with given prompt.

        Args:
            prompt: The prompt to send to CLI.
            phase: Phase identifier for tracking.

        Returns:
            Tuple of (success, duration_seconds, files_created, error).
        """
        start_time = time.time()

        cmd = [self.cli]
        if self.model:
            cmd.extend(["--model", self.model])
        cmd.extend(["--print", prompt])

        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=600,  # 10 minute timeout
            )
            duration = time.time() - start_time

            if result.returncode != 0:
                return (False, duration, [], result.stderr or "CLI returned non-zero")

            # Parse output for created files (implementation-specific)
            files_created = self._parse_files_created(result.stdout)
            return (True, duration, files_created, None)

        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            return (False, duration, [], "CLI timeout after 600 seconds")
        except FileNotFoundError:
            duration = time.time() - start_time
            return (False, duration, [], f"CLI '{self.cli}' not found")
        except Exception as e:
            duration = time.time() - start_time
            return (False, duration, [], str(e))

    def _parse_files_created(self, output: str) -> list[str]:
        """Parse CLI output to find created files.

        Args:
            output: CLI stdout output.

        Returns:
            List of file paths that were created.
        """
        # Simple heuristic: look for common file creation patterns
        files: list[str] = []
        for line in output.split("\n"):
            line = line.strip()
            if line.endswith(".py") and ("created" in line.lower() or "wrote" in line.lower()):
                # Extract file path
                parts = line.split()
                for part in parts:
                    if part.endswith(".py"):
                        files.append(part)
                        break
        return files

    def _infer_test_path(self, spec: SpecDocument) -> str:
        """Infer test file path from spec.

        Args:
            spec: The specification document.

        Returns:
            Path to test file.
        """
        name_slug = spec.name.lower().replace(" ", "_").replace("-", "_")
        return f"tests/test_{name_slug}.py"

    def _infer_impl_path(self, spec: SpecDocument) -> str:
        """Infer implementation file path from spec.

        Args:
            spec: The specification document.

        Returns:
            Path to implementation file.
        """
        if spec.target_path is not None:
            return str(spec.target_path)
        name_slug = spec.name.lower().replace(" ", "_").replace("-", "_")
        return f"src/{name_slug}.py"
