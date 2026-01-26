# Architecture

## Overview

Conductor bridges Claude Desktop to CLI coding agents. The key insight: Desktop stays lightweight (strategic), agents do heavy lifting (tactical).

## Components

### MCP Server (`src/server.py`)

Stdio-based MCP server exposing tools to Claude Desktop:
- Tool registration and schema
- Request routing to handlers
- JSON response formatting

### Codebase Mapper (`src/mapper/`)

Generates compressed project manifests for Desktop context efficiency. Optimized for synchronous execution (<2s).

```
mapper/
├── mapper.py            # Main mapping logic
├── detector.py          # Language and stack detection
├── parser.py            # AST-based Python module analysis
├── git_info.py          # Git history and status extraction
└── contracts.py         # Data structures
```

The mapper performs deep analysis of Python modules using the `PythonParser`, which leverages the `ast` module to extract:
- **Module-level docstrings** for high-level purpose identification.
- **Class structures**, including inheritance and public methods.
- **Function signatures** with type hints.
- **Key imports** to understand internal dependencies.

It also integrates Git context via `GitInfoExtractor` to provide:
- **Recent commit history** with lists of modified files.
- **Uncommitted changes** to identify work-in-progress.


### GUI Viewer (`src/gui_viewer.py`)

Real-time streaming output window:
- Parses stream-json from CLI agents
- Color-coded tool calls (READ=cyan, EDIT=gold, BASH=gold)
- Summary panel with stats
- Auto git commit on completion

### Task Tracker (`src/tasks/`)

Tracks dispatched tasks and results:
- Creates task records on dispatch
- GUI reports completion
- Desktop queries results

### Spec Engine (`src/specs/`)

Handles executable specification parsing and prompt building:
- Parses compact markdown specs (Interface, Must Do, Edge Cases)
- Generates system prompts for TDD-driven implementation
- Defines validation requirements (tests, lint, typecheck)

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
   │─── launch_claude_code ──▶│                          │
   │            OR            │─── spawn GUI + agent ───▶│
   │─── dispatch_with_spec ──▶│      (with spec prompt)  │
   │                          │                          │
   │◀── {task_id, status} ────│                          │
   │                          │                          │
   │                          │    ... agent works ...   │
   │                          │                          │
   │                          │◀─── completion ──────────│
   │                          │                          │
   │─── get_task_result ─────▶│                          │
   │◀── {summary, files} ─────│                          │
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
        "cmd": "gemini ...",
        "uses_stdin": True,
        "default_model": "gemini-2.5-flash"
    },
    "codex": {
        "cmd": "codex exec ...",
        "uses_stdin": False,
        "default_model": "gpt-5-codex"
    }
}
```

GUI viewer handles format differences transparently.
