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
├── detector.py          # Language and stack detection
├── parser.py            # AST-based Python module analysis
└── git_info.py          # Git history extraction (utility)
```

The mapper extracts high-level metadata from key Python modules:
- **Module-level docstrings** for purpose identification.
- **Class structures** and **Method signatures**.
- **Function signatures** with type hints.

To maintain sub-second latency, Git context (history/uncommitted changes) is excluded from the default mapping flow.

### GUI Viewer (`src/gui_viewer.py`)

Real-time streaming output window:
- Parses stream-json from CLI agents
- Color-coded tool calls (READ=cyan, EDIT=gold, BASH=gold)
- Summary panel with stats
- **Task Lifecycle**: Reports completion to Task Tracker and triggers automatic Git commit on success.

### Task Tracker (`src/tasks/`)

Tracks dispatched tasks and results:
- Creates task records on dispatch
- GUI reports completion
- Desktop queries results

### Spec Engine (`src/specs/`)

Handles executable specification parsing and prompt building:
- Parses compact markdown specs (Interface, Must Do, Edge Cases)
- **Validation**: Provides `validate_spec` for non-throwing verification of spec format and requirements.
- **Single-Phase Execution**: Implements a unified workflow managed by `SpecPhaseRunner`:
  - **Unified Prompt**: A single prompt instructs the agent to 1) implement the interface, then 2) write tests to verify all requirements.
  - **TDD Workflow**: Maintains TDD principles by requiring tests that validate the contract and behavior.
- **Spec-First Strategy**: Instructs agents to treat the specification as the source of truth, minimizing unnecessary codebase exploration to ensure strict adherence to the defined interface.
- **Circuit Breaker**: Implements an 8-read limit for specification-based tasks. If an agent makes more than 8 file reads without writing code, it is forced to stop exploration and begin implementation based on the spec.
- **Output Compression**: Instructs agents to summarize validation output (test results, linter errors) into compact formats to prevent context bloat during iterative development.
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
   │─── dispatch(content) ───▶│                          │
   │                          │─── DispatchGuard check ──┤
   │                          │    (running? duplicate?)  │
   │                          │                          │
   │◀── {status: "blocked"} ──┤ (if guard fails)         │
   │                          │                          │
   │                          │─── spawn GUI + agent ───▶│
   │                          │    (detects Spec/Prose)  │
   │                          │                          │
   │◀── {task_id, mode} ──────│                          │
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
