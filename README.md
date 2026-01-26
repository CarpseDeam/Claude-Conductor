# Conductor

> Bridge Claude Desktop to CLI coding agents (Claude Code, Gemini CLI, OpenAI Codex) with real-time streaming visualization.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)]()

One MCP tool. Multiple AI agents. Zero context switching.

## Features

- 🚀 **Dispatch coding tasks** to Claude Code, Gemini CLI, or OpenAI Codex from within Claude Desktop.
- 📊 **Live streaming GUI** with color-coded tool calls and progress updates.
- 🧠 **Codebase assimilation** - Generate compressed project knowledge (manifests) for Claude Desktop context.
- 🔄 **Task tracking** - Monitor status and results of background coding tasks.
- ⚡ **Non-blocking** - Desktop stays responsive while agents work in the background.

## Quick Start

### Prerequisites

- Python 3.11+
- At least one CLI agent installed and authenticated:
  - [Claude Code](https://github.com/anthropics/claude-code)
  - [Gemini CLI](https://github.com/google-gemini/gemini-cli)
  - [OpenAI Codex](https://github.com/openai/codex)

### Installation

Clone the repository and install in editable mode:

```bash
git clone https://github.com/yourusername/ClaudeDesktop-ClaudeCode-Bridge.git
cd ClaudeDesktop-ClaudeCode-Bridge
pip install -e .
```

### Configure Claude Desktop

Add the server to your `claude_desktop_config.json`:

**Windows:**
```json
{
  "mcpServers": {
    "conductor": {
      "command": "python",
      "args": ["-m", "src.server"],
      "cwd": "C:\\path\\to\\ClaudeDesktop-ClaudeCode-Bridge"
    }
  }
}
```

**macOS/Linux:**
```json
{
  "mcpServers": {
    "conductor": {
      "command": "python3",
      "args": ["-m", "src.server"],
      "cwd": "/path/to/ClaudeDesktop-ClaudeCode-Bridge"
    }
  }
}
```

## Usage

Once connected, you can interact with the bridge directly through Claude Desktop.

**Example Prompts:**

> "Get the manifest for my project at C:\Projects\MyAPI to understand the structure."

> "Launch Claude Code to add a password reset endpoint to the auth system in C:\Projects\MyAPI."

> "Have Gemini review the last changes in C:\Projects\MyAPI."

> "Check the status of my recent coding tasks."

## MCP Tools

The bridge provides the following tools to Claude Desktop:

| Tool | Description |
|------|-------------|
| `get_manifest` | Generates or retrieves a compressed strategic overview of a codebase (~1-2K tokens). Essential for giving Claude Desktop context before dispatching tasks. |
| `launch_claude_code` | Launches a CLI agent (Claude, Gemini, or Codex) in a visible terminal/GUI to execute a specific coding task. |
| `dispatch_assimilate` | Starts a background process to analyze a large codebase. Useful for initial setup of big projects where `get_manifest` might time out. |
| `get_task_result` | Retrieves the final status, modified files, and summary of a completed task. |
| `list_recent_tasks` | Lists the most recent dispatched tasks and their current statuses. |

### Tool Details

#### `launch_claude_code`
Dispatches a task to a CLI agent.
- **task**: Detailed description of the work to be done.
- **project_path**: Absolute path to the project root.
- **cli**: The agent to use (`claude`, `gemini`, or `codex`). Default is `claude`.
- **additional_paths**: Optional list of other directories the agent should have access to.

#### `get_manifest`
Retrieves a high-level summary of the project structure and key files.
- **project_path**: Absolute path to the project root.
- **quick**: (Optional) `true` for a fast scan, `false` for a deep analysis.
- **refresh**: (Optional) `true` to force a rebuild of the cached manifest.

## License

MIT