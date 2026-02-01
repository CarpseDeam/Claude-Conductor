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

### GUI Viewer (`src/gui_viewer.py`)

Real-time streaming output window:
- Parses stream-json from CLI agents
- Color-coded tool calls (READ=cyan, EDIT=gold, BASH=gold)
- Summary panel with stats
- **Task Lifecycle**: Reports completion to Task Tracker and triggers automatic Git commit on success. Reports failure if the window is closed before the task finishes.

### Task Tracker (`src/tasks/`)

Tracks dispatched tasks and results:
- Creates task records on dispatch
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
Desktop                    Conductor                 CLI Agent
   │                          │                          │
   │─── dispatch(content) ───▶│                          │
   │                          │─── DispatchGuard check ──┤
   │                          │    (running? duplicate?)  │
   │                          │                          │
   │◀── {status: "blocked"} ──┤ (if guard fails)         │
   │                          │                          │
   │                          │─── spawn GUI + agent ───▶│
   │                          │                          │
   │◀── {task_id} ────────────│                          │
   │                          │                          │
   │                          │    ... agent works ...   │
   │                          │                          │
   │                          │◀─── completion ──────────│
   │                          │                          │
   │─── get_task_result ─────▶│                          │
   │◀── {summary, files, cli_output} ─│                  │
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
