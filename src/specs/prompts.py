"""Prompt templates for spec-driven development."""

from .contracts import SpecDocument, SpecTier


class SpecPromptBuilder:
    """Builds CLI prompts for spec expansion and implementation."""

    MAX_ITERATIONS: int = 5

    def __init__(self, language: str = "python") -> None:
        """Initialize builder with detected language.

        Args:
            language: The detected project language (e.g., "python", "gdscript").
        """
        self.language = language

    def build_prompt(self, spec: SpecDocument) -> str:
        """Build unified prompt for single-phase spec execution.

        Instructs the agent to:
        1. Implement the interface
        2. Write tests that verify each Must Do item
        3. Write tests for each Edge Case

        Tests validate contract/behavior, not implementation details.

        Args:
            spec: The specification document.

        Returns:
            Prompt string for unified implementation and test generation.
        """
        impl_path = self._infer_impl_path(spec)
        test_path = self._infer_test_path(spec)
        tier_guidance = self._get_tier_guidance(spec.tier)

        sections = [
            "# Spec-Driven Implementation",
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
            "The spec tells you exactly what to build. Trust it.",
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
            "## YOUR TASK",
            "",
            tier_guidance,
            "",
            "### Step 1: Implement the Interface",
            "",
            f"Implementation location: `{impl_path}`",
            "",
            "Implementation Rules:",
            "1. Follow interface signatures EXACTLY as specified",
            "2. Handle all edge cases as specified",
            "3. Ensure preconditions are checked",
            "4. Ensure postconditions are satisfied",
            "5. Respect all 'Must Not Do' constraints",
            "",
            "### Step 2: Write Tests",
            "",
            f"Test file location: `{test_path}`",
            "",
            "After implementing, write tests that verify contract and behavior:",
            "",
            "**Must Do Tests:**",
            "- Write one test for each item in the 'Must Do' section",
            "- Tests should verify the behavior/contract, not implementation details",
        ]

        if spec.edge_cases:
            sections.extend([
                "",
                "**Edge Case Tests:**",
                "- Write one test for each edge case specified",
            ])

        test_guidance = self._get_test_guidance(self.language)
        sections.extend([
            "",
            "Test Code Requirements:",
            test_guidance,
            "",
            "### Step 3: Validate",
            "",
            f"Run validation: `{spec.validation.tests}`",
            "",
            "Iterate until all tests pass.",
            f"Maximum iterations: {self.MAX_ITERATIONS}",
        ])

        return "\n".join(sections)

    def _get_test_guidance(self, language: str) -> str:
        """Return test framework guidance based on language.

        Args:
            language: The detected project language.

        Returns:
            Test framework guidance string for the prompt.
        """
        if language == "gdscript":
            return (
                "- Use GUT (Godot Unit Test) framework\n"
                "- Test class extends GutTest\n"
                "- Use assert_eq(), assert_true(), assert_false(), assert_null()\n"
                "- Use before_each() and after_each() for setup/teardown\n"
                "- Test files: res://tests/test_*.gd\n"
                "- Use descriptive test names (test_player_takes_damage)\n"
                "- Keep tests focused and independent"
            )
        else:
            return (
                "- Use pytest fixtures for shared setup\n"
                "- Include full type hints\n"
                "- Use descriptive test names\n"
                "- Keep tests focused and independent"
            )

    def _get_tier_guidance(self, tier: SpecTier) -> str:
        """Return tier-specific guidance for test depth."""
        guidance_map = {
            SpecTier.HOTFIX: (
                "**Tier: HOTFIX** - Minimal scope, fast iteration.\n"
                "- Focus on the specific bug/issue only\n"
                "- 1-3 targeted tests maximum"
            ),
            SpecTier.FEATURE: (
                "**Tier: FEATURE** - Standard feature implementation.\n"
                "- Full behavior test coverage\n"
                "- All edge cases must be tested\n"
                "- Contract tests for public interfaces"
            ),
            SpecTier.SYSTEM: (
                "**Tier: SYSTEM** - Comprehensive system component.\n"
                "- Exhaustive test coverage required\n"
                "- Integration tests if multiple modules involved\n"
                "- Full contract testing including invariants"
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
