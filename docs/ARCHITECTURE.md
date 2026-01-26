# Architecture

## Overview

Conductor bridges Claude Desktop to CLI coding agents. The key insight: Desktop stays lightweight (strategic), agents do heavy lifting (tactical).

## Components

### MCP Server (`src/server.py`)

Stdio-based MCP server exposing tools to Claude Desktop:
- Tool registration and schema
- Request routing to handlers
- JSON response formatting

### Codebase Assimilator (`src/assimilator/`)

Generates compressed project manifests for Desktop context efficiency.

```
assimilator/
├── core.py              # Orchestrator
├── manifest.py          # Data contracts
├── analyzers/           # Extract project info
│   ├── python_analyzer.py
│   ├── structure_analyzer.py
│   └── git_analyzer.py
├── extractors/          # Extract patterns/symbols
│   ├── imports.py
│   ├── symbols.py
│   └── patterns.py
└── output/
    ├── formatter.py     # Compress for LLM
    └── cache.py         # Cache invalidation
```

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
Project Files → Analyzers → Extractors → Manifest → Cache
                   │            │           │
                   ▼            ▼           ▼
              Structure    Patterns    ~1.5K tokens
              Symbols      Imports     (compressed)
```

### Task Dispatch

```
Desktop                    Conductor                 CLI Agent
   │                          │                          │
   │─── launch_claude_code ──▶│                          │
   │                          │─── spawn GUI + agent ───▶│
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
