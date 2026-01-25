# Conductor

> Bridge Claude Desktop to CLI coding agents with real-time streaming visualization

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)]()

One MCP tool. Multiple AI agents. Zero context switching.

## Features

- 🚀 **Dispatch coding tasks** to Claude Code, Gemini CLI, or OpenAI Codex
- 📊 **Live streaming GUI** with color-coded tool calls
- 🧠 **Codebase assimilation** - compressed project knowledge for Desktop
- 🔄 **Auto git commits** with AI-generated messages (Ollama)
- 📝 **Auto documentation** - Gemini keeps docs fresh after every commit
- ⚡ **Non-blocking** - Desktop stays responsive while agents work

## Quick Start

### Prerequisites

- Python 3.11+
- At least one CLI agent installed:
  - [Claude Code](https://github.com/anthropics/claude-code)
  - [Gemini CLI](https://github.com/google-gemini/gemini-cli)
  - [OpenAI Codex](https://github.com/openai/codex)

### Install

```bash
pip install -e .
```

### Configure Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "conductor": {
      "command": "python",
      "args": ["-m", "src.server"],
      "cwd": "C:\\Projects\\ClaudeDesktop-ClaudeCode-Bridge"
    }
  }
}
```

### Usage

Just talk to Claude Desktop:

> "Get the manifest for my project at C:\Projects\my-api"

> "Add password reset to the auth system"

> "Have Gemini review the last changes"

## MCP Tools

| Tool | Purpose |
|------|---------|
| `get_manifest` | Get compressed codebase knowledge (~1-2K tokens) |
| `launch_claude_code` | Dispatch coding task to any CLI agent |
| `get_task_result` | Get results after task completion |
| `list_recent_tasks` | See recent dispatches |
| `dispatch_assimilate` | Background codebase analysis |

See [API Reference](docs/API.md) for full documentation.

## How It Works

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Claude Desktop │────▶│    Conductor    │────▶│   CLI Agent     │
│   (strategic)   │ MCP │  (orchestrator) │     │  (tactical)     │
└─────────────────┘     └────────┬────────┘     └────────┬────────┘
                                 │                       │
                                 ▼                       ▼
                        ┌─────────────────┐     ┌─────────────────┐
                        │    Manifest     │     │   Streaming     │
                        │    (cached)     │     │      GUI        │
                        └─────────────────┘     └─────────────────┘
```

See [Architecture](docs/ARCHITECTURE.md) for details.

## License

MIT
