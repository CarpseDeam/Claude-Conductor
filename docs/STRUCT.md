# ClaudeDesktop-ClaudeCode-Bridge

**Language:** python

## Structure

- `.claude/` - Project-level steering (1 file)
- `docs/` - Documentation (4 files)
- `src/` - Source code (3 files)
- `src/dispatch/` - Task dispatch logic (2 files)
- `src/git/` - Git operations and workflows (5 files)
- `src/gui/` - PySide6 GUI implementation (4 files)
- `src/mapper/` - Codebase mapping and detection (5 files)
- `src/output/` - Output compression and masking (2 files)
- `src/pipelines/` - Background automation (4 files)
- `src/tasks/` - Task tracking and persistence (3 files)
- `src/utils/` - Utility functions (2 files)
- `tests/` - Test suite

## Key Files

- `.claude\steering.md` - Project standards and stack info (Auto-generated)
- `src\server.py` - MCP Server entry and Steering generation
- `src\mapper\detector.py` - Stack and language detection (Python, Godot)
- `src\dispatch\handler.py` - Task dispatch orchestration
- `src\gui\viewer.py` - PySide6 GUI implementation
- `src\gui_viewer.py` - GUI entry point (Subprocess wrapper)
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

### `src\gui_viewer.py`
_GUI entry point. Launched as a subprocess by server.py._

### `src\gui\`
_PySide6 real-time output viewer with modular formatting and theming._

**ClaudeOutputWindow**: Main window handling process execution and UI updates.
**Formatters**: HTML formatting for Claude and Gemini JSON streams.
**Theme**: Centralized CSS and color palette.

### `src\tasks\tracker.py`
_Task tracking and persistence._

**TaskTracker**: `create_task`, `complete_task`, `fail_task`, `get_task`, `get_recent_tasks`

## Stats

- Files: ~60
- Directories: 16
- Lines: ~3000
