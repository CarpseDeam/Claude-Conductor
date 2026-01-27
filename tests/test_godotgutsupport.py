"""Tests for Godot/GUT support in the bridge."""

from pathlib import Path

import pytest

from src.mapper.detector import StackDetector, StackInfo
from src.specs.prompts import SpecPromptBuilder
from src.server import ClaudeCodeMCPServer


class FakeCodebaseMap:
    """Fake codebase map for testing steering file generation."""

    def __init__(self, project_name: str, stack: StackInfo) -> None:
        self.project_name = project_name
        self.stack = stack


@pytest.fixture
def detector() -> StackDetector:
    return StackDetector()


@pytest.fixture
def server() -> ClaudeCodeMCPServer:
    return ClaudeCodeMCPServer()


class TestGodotDetection:
    """Tests for Godot project detection."""

    def test_detect_godot_project_by_project_godot_file(
        self, detector: StackDetector, tmp_path: Path
    ) -> None:
        """Detect Godot project by checking for project.godot file."""
        (tmp_path / "project.godot").write_text("[config]\nname=\"TestGame\"")

        result = detector.detect(tmp_path)

        assert result.language == "gdscript"

    def test_godot_detected_sets_language_to_gdscript(
        self, detector: StackDetector, tmp_path: Path
    ) -> None:
        """When Godot detected: set StackInfo.language to gdscript."""
        (tmp_path / "project.godot").write_text("")

        result = detector.detect(tmp_path)

        assert result.language == "gdscript"
        assert isinstance(result, StackInfo)

    def test_godot_detection_does_not_require_gut_installed(
        self, detector: StackDetector, tmp_path: Path
    ) -> None:
        """Detection works without GUT addon present."""
        (tmp_path / "project.godot").write_text("")
        # No addons/gut directory

        result = detector.detect(tmp_path)

        assert result.language == "gdscript"

    def test_no_project_godot_falls_back_to_python_detection(
        self, detector: StackDetector, tmp_path: Path
    ) -> None:
        """Without project.godot, falls back to Python detection."""
        (tmp_path / "pyproject.toml").write_text("[tool.pytest]")

        result = detector.detect(tmp_path)

        assert result.language == "python"

    def test_no_config_files_returns_unknown(
        self, detector: StackDetector, tmp_path: Path
    ) -> None:
        """No config files returns unknown language."""
        result = detector.detect(tmp_path)

        assert result.language == "unknown"


class TestGodotPriority:
    """Tests for Godot detection priority over other languages."""

    def test_godot_and_python_project_prefers_godot(
        self, detector: StackDetector, tmp_path: Path
    ) -> None:
        """Project with both project.godot AND pyproject.toml prefers Godot."""
        (tmp_path / "project.godot").write_text("")
        (tmp_path / "pyproject.toml").write_text("[tool.pytest]")

        result = detector.detect(tmp_path)

        assert result.language == "gdscript"


class TestGodotSteeringFile:
    """Tests for Godot steering file generation."""

    def test_godot_steering_includes_gut_environment_section(
        self, server: ClaudeCodeMCPServer, tmp_path: Path
    ) -> None:
        """Steering file for Godot projects includes GUT environment section."""
        stack = StackInfo(
            language="gdscript",
            frameworks=[],
            tools=[],
            package_manager=None,
        )
        codebase_map = FakeCodebaseMap("TestGame", stack)

        server._generate_steering_file(tmp_path, codebase_map)

        steering = (tmp_path / ".claude" / "steering.md").read_text()
        assert "GUT" in steering
        assert "godot --headless" in steering

    def test_godot_steering_does_not_mention_pytest(
        self, server: ClaudeCodeMCPServer, tmp_path: Path
    ) -> None:
        """Steering file for Godot should NOT mention pytest."""
        stack = StackInfo(
            language="gdscript",
            frameworks=[],
            tools=[],
            package_manager=None,
        )
        codebase_map = FakeCodebaseMap("TestGame", stack)

        server._generate_steering_file(tmp_path, codebase_map)

        steering = (tmp_path / ".claude" / "steering.md").read_text()
        assert "pytest" not in steering.lower()

    def test_godot_steering_notes_gut_not_installed(
        self, server: ClaudeCodeMCPServer, tmp_path: Path
    ) -> None:
        """When GUT addon not present, notes it needs to be installed."""
        stack = StackInfo(
            language="gdscript",
            frameworks=[],
            tools=[],
            package_manager=None,
        )
        codebase_map = FakeCodebaseMap("TestGame", stack)

        server._generate_steering_file(tmp_path, codebase_map)

        steering = (tmp_path / ".claude" / "steering.md").read_text()
        assert "GUT addon not found" in steering or "Install" in steering

    def test_godot_steering_no_install_note_when_gut_present(
        self, server: ClaudeCodeMCPServer, tmp_path: Path
    ) -> None:
        """When GUT addon is present, no install note needed."""
        (tmp_path / "addons" / "gut").mkdir(parents=True)
        stack = StackInfo(
            language="gdscript",
            frameworks=[],
            tools=[],
            package_manager=None,
        )
        codebase_map = FakeCodebaseMap("TestGame", stack)

        server._generate_steering_file(tmp_path, codebase_map)

        steering = (tmp_path / ".claude" / "steering.md").read_text()
        assert "GUT addon not found" not in steering


class TestGdscriptTestGuidance:
    """Tests for GDScript test guidance in spec prompts."""

    def test_gdscript_prompt_uses_gut_patterns(self) -> None:
        """Spec prompt for GDScript should use GUT test patterns."""
        builder = SpecPromptBuilder(language="gdscript")

        guidance = builder._get_test_guidance("gdscript")

        assert "GUT" in guidance
        assert "extends GutTest" in guidance
        assert "assert_eq" in guidance
        assert "assert_true" in guidance

    def test_gdscript_prompt_references_test_path_convention(self) -> None:
        """Spec prompt for GDScript should reference res://tests/test_*.gd."""
        builder = SpecPromptBuilder(language="gdscript")

        guidance = builder._get_test_guidance("gdscript")

        assert "res://tests/test_*.gd" in guidance

    def test_python_prompt_uses_pytest_patterns(self) -> None:
        """Python prompt should use pytest patterns, not GUT."""
        builder = SpecPromptBuilder(language="python")

        guidance = builder._get_test_guidance("python")

        assert "pytest" in guidance
        assert "GUT" not in guidance


class TestLanguagePassthrough:
    """Tests for language passthrough from StackInfo to prompt builder."""

    def test_prompt_builder_accepts_language_parameter(self) -> None:
        """SpecPromptBuilder should accept language parameter."""
        builder = SpecPromptBuilder(language="gdscript")

        assert builder.language == "gdscript"

    def test_prompt_builder_defaults_to_python(self) -> None:
        """SpecPromptBuilder should default to python."""
        builder = SpecPromptBuilder()

        assert builder.language == "python"


class TestExistingPythonFlow:
    """Tests ensuring Python/pytest flow is not broken."""

    def test_python_project_detection_unchanged(
        self, detector: StackDetector, tmp_path: Path
    ) -> None:
        """Python project detection still works."""
        (tmp_path / "pyproject.toml").write_text("[tool.pytest]\n[dependencies]\nfastapi = \"*\"")

        result = detector.detect(tmp_path)

        assert result.language == "python"
        assert "FastAPI" in result.frameworks

    def test_python_steering_includes_pytest(
        self, server: ClaudeCodeMCPServer, tmp_path: Path
    ) -> None:
        """Python steering still includes pytest."""
        stack = StackInfo(
            language="python",
            frameworks=["FastAPI"],
            tools=["pytest"],
            package_manager="pip",
        )
        codebase_map = FakeCodebaseMap("TestProject", stack)

        server._generate_steering_file(tmp_path, codebase_map)

        steering = (tmp_path / ".claude" / "steering.md").read_text()
        assert "pytest" in steering
