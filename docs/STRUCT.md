# ClaudeDesktop-ClaudeCode-Bridge

**Language:** python

## Structure

- `.claude/` - Project-level steering (1 file)
- `docs/` - Documentation (4 files)
- `src/` - Source code (3 files)
- `src/dispatch/` - Task dispatch logic (2 files)
- `src/git/` - Git operations and workflows (5 files)
- `src/mapper/` - Codebase mapping and detection (5 files)
- `src/output/` - Output compression and masking (2 files)
- `src/pipelines/` - Background automation (4 files)
- `src/specs/` - Spec-driven development engine (6 files)
- `src/tasks/` - Task tracking and persistence (3 files)
- `src/utils/` - Utility functions (2 files)
- `tests/` - Test suite

## Key Files

- `.claude\steering.md` - Project standards and stack info (Auto-generated)
- `src\server.py` - MCP Server entry and Steering generation
- `src\mapper\detector.py` - Stack and language detection (Python, Godot)
- `src\dispatch\handler.py` - Task dispatch orchestration
- `src\specs\prompts.py` - Language-aware prompt templates
- `src\specs\runner.py` - Unified spec execution runner
- `src\gui_viewer.py` - Streaming output and command detection
- `pyproject.toml` - Project configuration
- `README.md` - Documentation

## Module Details

### `src\server.py`
_MCP Server entry and project steering._

**ClaudeCodeMCPServer**: `_generate_godot_steering`, `_generate_python_steering`
**DispatchGuard**: `check_running_task`, `check_duplicate`, `record_dispatch`

### `src\mapper\detector.py`
_Language and stack detection logic._

**StackDetector**: `detect(project_path)` - Now supports Godot (GDScript) priority detection.

### `src\specs\prompts.py`
_Language-aware prompt templates for spec-driven development._

**SpecPromptBuilder**: `_get_test_guidance(language)` - Provides framework-specific instructions (GUT/pytest).

### `src\specs\runner.py`
_Orchestrates spec execution with language context._

**SpecPhaseRunner**: Now initialized with project `language`.

### `src\gui_viewer.py`
_Real-time output viewer with enhanced command detection._

**Functions**: `_detect_command_type(cmd)` - Robust detection for pytest, mypy, and linting.

## Stats

- Files: ~45
- Directories: 13
- Lines: ~4000
