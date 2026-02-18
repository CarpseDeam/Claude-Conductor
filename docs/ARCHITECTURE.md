# Architecture

## Overview

Conductor bridges Claude Desktop to CLI coding agents. The key insight: Desktop stays lightweight (strategic), agents do heavy lifting (tactical).

## Components

### MCP Server (`src/server.py`)

Stdio-based MCP server exposing tools to Claude Desktop:
- Tool registration and schema
- Request routing to handlers
- **DispatchGuard**: Prevents concurrent tasks for the same project and deduplicates identical requests within a 5-minute window.
- JSON response formatting

### Codebase Mapper (`src/mapper/`)

Generates compressed project manifests for Desktop context efficiency. Optimized for high-speed synchronous execution (<1s) by using a shallow directory walk (depth=2) and identifying key files by name patterns before performing AST enrichment.

```
mapper/
├── mapper.py            # Main mapping logic (shallow walk + key files)
├── detector.py          # Language and stack detection (Python, Godot)
├── parser.py            # AST-based Python module analysis
└── git_info.py          # Git history extraction (utility)
```

The mapper extracts high-level metadata from key Python modules (or project configuration for Godot). The `StackDetector` prioritized Godot (`project.godot`) to ensure proper steering and testing guidance for game projects.

### GUI Viewer (`src/gui/`)

PySide6-based real-time streaming output window:
- Parses stream-json from CLI agents
- HTML-based color coding (READ, EDIT, BASH) with modular formatters
- Centralized theming (`gui/theme.py`) with enhanced legibility (larger fonts/padding)
- Summary panel with stats
- **Task Lifecycle**: Supports multiple turns within a single window. The window starts a `SessionListener` (TCP server) and registers its port in the `TaskTracker`. Subsequent prompts for the same project are routed to the existing window.
- **Session Persistence**: Captures `session_id` from initial Claude CLI output and uses `--resume <session_id>` for follow-up turns.
- **Subprocess Entry**: `src/gui_viewer.py` provides the CLI interface for launching the window. The server attempts to use the project's `.venv` Python interpreter to ensure PySide6 dependencies are met, and errors are captured in `src/_gui_error.log`.

### Task Tracker (`src/tasks/`)

Tracks dispatched tasks and results:
- Creates task records on dispatch
- Stores `session_id` and `socket_port` for persistent session routing
- GUI reports completion
- Desktop queries results

### Git Workflow (`src/git/`)

Automated commits with AI-generated messages:
- Ollama (mistral:latest) generates commit messages
- Branch management for feature work
- Push/merge automation

### Post-Commit Pipelines (`src/pipelines/`)

Background agents triggered after commits:
- Auto-documentation (Gemini Flash)
- Configurable per-project
- **Reliable Dispatch**: Uses temporary files and shell pipes to handle large diffs and ensure Windows compatibility.

## Data Flow

### Manifest Generation

```
Project Files → Mapper → Detector → Codebase Map → Markdown
                   │         │          │           │
                   ▼         ▼          ▼           ▼
              Structure   Stack      ~1K tokens   STRUCT.md
              Files       Lang       (optimized)
```

### Task Dispatch

```
Desktop                    Conductor                 GUI Session
   │                          │                          │
   │─── dispatch(content) ───▶│                          │
   │                          │─── DispatchGuard check ──┤
   │                          │    (active session?)     │
   │                          │                          │
   │◀── {status: "followup"} ─┼────── send prompt ──────▶│
   │    (if session exists)   │                          │─── next turn ───▶ CLI Agent
   │                          │                          │
   │                          │─── spawn GUI + agent ───▶│
   │                          │    (if no session)       │
   │                          │                          │
   │◀── {task_id} ────────────│                          │
```

## CLI Backend Abstraction

All CLI agents use unified config:

```python
CLI_CONFIGS = {
    "claude": {
        "cmd": "claude -p ...",
        "uses_stdin": True,
        "default_model": "opus"
    },
    "gemini": {
        "cmd": "gemini --output-format stream-json --approval-mode yolo",
        "uses_stdin": True,
        "default_model": "gemini-2.5-pro"
    },
    "codex": {
        "cmd": "codex exec ...",
        "uses_stdin": False,
        "default_model": "gpt-5-codex"
    }
}
```

GUI viewer handles format differences transparently.
