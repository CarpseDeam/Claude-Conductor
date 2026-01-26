"""Prompt templates for spec-driven development."""

import warnings

from .contracts import SpecDocument, SpecTier


class SpecPromptBuilder:
    """Builds CLI prompts for spec expansion and implementation."""

    MAX_ITERATIONS: int = 5

    def build_phase1_prompt(self, spec: SpecDocument) -> str:
        """Build prompt for test generation only (Phase 1).

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
        """Build prompt for implementation against existing tests (Phase 2).

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

        Build compound prompt for complete spec-driven workflow.
        This single-phase approach is deprecated in favor of two-phase execution.

        Args:
            spec: The specification document to expand.

        Returns:
            Complete prompt string for CLI agent.
        """
        warnings.warn(
            "build_full_prompt is deprecated. Use build_phase1_prompt and "
            "build_phase2_prompt for two-phase execution.",
            DeprecationWarning,
            stacklevel=2,
        )
        sections = [
            "# Spec-Driven Implementation Task",
            "",
            "You are implementing a feature from a formal specification. "
            "Follow this workflow exactly.",
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
            "",
            "The spec tells you exactly what to build and where. Trust it.",
            "",
            "## CIRCUIT BREAKER",
            "",
            "If you have made 8+ file reads without writing any code, STOP.",
            "You are exploring instead of implementing. The spec is complete.",
            "Write the implementation now with what you know.",
            "",
            "## THE SPECIFICATION",
            "",
            spec.to_prompt_context(),
            "",
            self._build_test_expansion_section(spec),
            "",
            self._build_implementation_section(spec),
            "",
            self._build_validation_section(spec),
            "",
            self._build_failure_protocol(),
        ]
        return "\n".join(sections)

    def _build_test_expansion_section(self, spec: SpecDocument) -> str:
        """Instructions for expanding spec into test suite."""
        test_path = self._infer_test_path(spec)
        tier_guidance = self._get_tier_guidance(spec.tier)

        lines = [
            "## PHASE 1: EXPAND SPEC INTO TESTS",
            "",
            tier_guidance,
            "",
            "Create a pytest test suite that captures the specification.",
            "",
            f"Test file location: `{test_path}`",
            "",
            "### Test Generation Rules",
            "",
            "1. **Behavior Tests**: Create one test per 'Must Do' requirement",
            "2. **Edge Case Tests**: Create one test per edge case",
            "3. **Contract Tests**: Generate tests for:",
            "   - Precondition violations (should raise appropriate errors)",
            "   - Postcondition verification (outputs match expected)",
            "   - Invariant preservation (state remains valid)",
            "4. **Constraint Tests**: Verify 'Must Not Do' constraints are not violated",
            "",
            "### Test Code Requirements",
            "",
            "- Use pytest fixtures for shared setup",
            "- Include full type hints",
            "- Use descriptive test names: `test_{behavior}_when_{condition}`",
            "- Keep tests focused and independent",
            "- Use `pytest.raises` for expected exceptions",
            "- Use `pytest.mark.parametrize` for variations where appropriate",
            "",
            "Write all tests BEFORE implementing. Tests should initially fail.",
        ]
        return "\n".join(lines)

    def _build_implementation_section(self, spec: SpecDocument) -> str:
        """Instructions for implementing against tests."""
        impl_path = self._infer_impl_path(spec)

        lines = [
            "## PHASE 2: IMPLEMENT",
            "",
            f"Implementation location: `{impl_path}`",
            "",
            "### Implementation Rules",
            "",
            "1. Follow interface signatures EXACTLY as specified",
            "2. Implement minimal code to pass all tests",
            "3. Respect all 'Must Not Do' constraints",
            "4. Handle all edge cases as specified",
            "5. Ensure preconditions are checked",
            "6. Ensure postconditions are satisfied",
            "7. Preserve all invariants",
            "",
            "### Code Quality",
            "",
            "- Use full type hints matching the interface",
            "- Follow single responsibility principle",
            "- Keep functions focused and small",
            "- No dead code or unused imports",
        ]
        return "\n".join(lines)

    def _build_validation_section(self, spec: SpecDocument) -> str:
        """Instructions for running validation and iteration."""
        validation = spec.validation

        lines = [
            "## PHASE 3: VALIDATE AND ITERATE",
            "",
            "Run validation commands and fix issues until all pass.",
            "",
            f"Maximum iterations: {self.MAX_ITERATIONS}",
            "",
            "### Validation Steps",
            "",
            f"1. **Run Tests**: `{validation.tests}`",
            "   - If tests fail: analyze failures, fix implementation, retry",
            "   - Do NOT modify tests unless spec is ambiguous",
        ]

        if validation.typecheck:
            lines.append(f"2. **Type Check**: `{validation.typecheck}`")
            lines.append("   - Fix any type errors before proceeding")

        if validation.lint:
            step_num = 3 if validation.typecheck else 2
            lines.append(f"{step_num}. **Lint**: `{validation.lint}`")
            lines.append("   - Fix lint errors")

        lines.extend([
            "",
            "### Iteration Loop",
            "",
            "```",
            "for iteration in 1..5:",
            "    run tests",
            "    if all pass:",
            "        run typecheck (if specified)",
            "        run lint (if specified)",
            "        if all pass: SUCCESS - report completion",
            "    else:",
            "        analyze failures",
            "        fix implementation (not tests)",
            "        continue",
            "```",
            "",
            "### Output Compression",
            "",
            "After each validation command, DO NOT keep full raw output in your context.",
            "Instead, immediately summarize to:",
            "",
            "```",
            "pytest: ✓ 15 passed | ✗ 3 failed, 12 passed",
            "mypy: ✓ Success | ✗ 5 errors (file:line:msg)",
            "lint: ✓ clean | ✗ 3 errors",
            "```",
            "",
            "For failures, note ONLY:",
            "- File path and line number",
            "- Error message (one line)",
            "- Skip stack traces, skip passing test details",
            "",
            "This prevents context bloat during iteration.",
            "",
            "On SUCCESS, report:",
            "- All tests passing",
            "- Files created/modified",
            "- Any notes on implementation decisions",
        ])
        return "\n".join(lines)

    def _build_failure_protocol(self) -> str:
        """Instructions for handling implementation failure."""
        lines = [
            "## FAILURE PROTOCOL",
            "",
            f"If after {self.MAX_ITERATIONS} iterations tests still fail, report:",
            "",
            "```",
            "## SPEC IMPLEMENTATION FAILED",
            "",
            "### Passing Tests",
            "- [list passing test names]",
            "",
            "### Failing Tests",
            "- test_name: [error message summary]",
            "",
            "### Proposed Spec Amendment",
            "[If the spec itself seems problematic, suggest specific changes]",
            "",
            "### Raw Output",
            "[Last test run output, truncated if very long]",
            "```",
            "",
            "Do NOT continue past 5 failed iterations. Report and stop.",
        ]
        return "\n".join(lines)

    def _get_tier_guidance(self, tier: SpecTier) -> str:
        """Return tier-specific guidance for test depth."""
        guidance_map = {
            SpecTier.HOTFIX: (
                "**Tier: HOTFIX** - Minimal scope, fast iteration.\n"
                "- Focus on the specific bug/issue only\n"
                "- 1-3 targeted tests maximum\n"
                "- Inline implementation preferred\n"
                "- Skip exhaustive edge case testing"
            ),
            SpecTier.FEATURE: (
                "**Tier: FEATURE** - Standard feature implementation.\n"
                "- Full behavior test coverage\n"
                "- All edge cases must be tested\n"
                "- Single module implementation\n"
                "- Contract tests for public interfaces"
            ),
            SpecTier.SYSTEM: (
                "**Tier: SYSTEM** - Comprehensive system component.\n"
                "- Exhaustive test coverage required\n"
                "- Integration tests if multiple modules involved\n"
                "- May span multiple files\n"
                "- Full contract testing including invariants\n"
                "- Consider performance implications"
            ),
        }
        return guidance_map[tier]

    def _infer_test_path(self, spec: SpecDocument) -> str:
        """Infer test file path from spec."""
        name_slug = spec.name.lower().replace(" ", "_").replace("-", "_")
        return f"tests/test_{name_slug}.py"

    def _infer_impl_path(self, spec: SpecDocument) -> str:
        """Infer implementation file path from spec."""
        if spec.target_path:
            return spec.target_path
        name_slug = spec.name.lower().replace(" ", "_").replace("-", "_")
        return f"src/{name_slug}.py"
