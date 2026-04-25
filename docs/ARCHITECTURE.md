# Architecture

## Overview

Conductor bridges Claude Desktop to CLI coding agents. The key insight: Desktop stays lightweight (strategic), agents do heavy lifting (tactical).

## Components

### MCP Server (`src/server.py`)

Stdio-based MCP server exposing tools to Claude Desktop:
- Tool registration and schema
- Request routing to handlers
- **DispatchGuard**: Prevents concurrent tasks for the same project and deduplicates identical requests. Includes socket probing to verify active sessions and enforces a 30-minute session max age.
- **Intent Guidance**: System prompt instructs agents to treat dispatch as intent rather than a strict blueprint, follow existing patterns, stay strictly in scope, and prioritize tool call efficiency with minimal, targeted testing.
- JSON response formatting

### Codebase Mapper (`src/mapper/`) [INTERNAL]

Optimized for high-speed project analysis. While no longer exposed as a direct MCP tool (as modern CLI agents handle discovery autonomously), the mapper remains in the codebase as a utility for generating compressed manifests if needed.

```
mapper/
├── mapper.py            # Main mapping logic (shallow walk + key files)
├── detector.py          # Language and stack detection (Python, Godot)
├── parser.py            # AST-based Python module analysis
└── git_info.py          # Git history extraction (utility)
```

### GUI Viewer (`src/gui/`)

PySide6-based real-time streaming output window:
- Parses stream-json from CLI agents
- HTML-based color coding (READ, EDIT, BASH) with modular formatters. Now uses `white-space:pre-wrap` to preserve whitespace in text deltas.
- Centralized theming (`gui/theme.py`) with enhanced legibility
- Summary panel with turn-based stats
- **Task Lifecycle**: Supports multiple turns within a single window. The window starts a `SessionListener` (TCP server) and registers its port in the `TaskTracker`.
- **Session Persistence**: Merges modified file lists and summaries across turns in the `TaskTracker`.
- **Subprocess Entry**: `src/gui_viewer.py` launches the window using the project's `.venv` if available.

### Task Tracker (`src/tasks/`)

Tracks dispatched tasks and results:
- Creates task records on dispatch
- Stores `session_id` and `socket_port` for persistent session routing
- Merges results across multiple turns in a single session
- GUI reports completion/failure

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

### Task Dispatch

```
Desktop                    Conductor                 GUI Session
   │                          │                          │
   │─── dispatch(content) ───▶│                          │
   │                          │─── DispatchGuard check ──┤
   │                          │    (socket probe)        │
   │                          │                          │
   │◀── {status: "followup"} ─┼────── send prompt ──────▶│
   │    (if session alive)    │                          │─── next turn ───▶ CLI Agent
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
