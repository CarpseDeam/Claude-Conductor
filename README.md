# Conductor

> Bridge Claude Desktop to CLI coding agents (Claude Code, Gemini CLI, OpenAI Codex) with real-time streaming visualization.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)]()

One MCP tool. Multiple AI agents. Zero context switching.

## Features

- **Dispatch coding tasks** to Claude Code, Gemini CLI, or OpenAI Codex from within Claude Desktop
- **Live streaming GUI** with color-coded tool calls and progress updates
- **Codebase assimilation** - Generate compressed project knowledge (manifests) for Claude Desktop context
- **Task tracking** - Monitor status and results of background coding tasks
- **Non-blocking** - Desktop stays responsive while agents work in the background

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
git clone https://github.com/anthropics/ClaudeDesktop-ClaudeCode-Bridge.git
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

Once connected, interact with the bridge through Claude Desktop.

**Example Prompts:**

> "Get the manifest for my project at /home/user/projects/myapi to understand the structure."

> "Launch Claude Code to add a password reset endpoint to the auth system in /home/user/projects/myapi."

> "Have Gemini review the last changes in /home/user/projects/myapi."

> "Check the status of my recent coding tasks."

## MCP Tools

### get_manifest

Generates or retrieves a compressed strategic overview of a codebase (~1-2K tokens). Call this first before dispatching coding tasks to give Claude Desktop context about the project.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `project_path` | string | Yes | Absolute path to project root |
| `quick` | boolean | No | Fast shallow analysis (default: true). Set to false for deep analysis |
| `refresh` | boolean | No | Force rebuild manifest, ignore cache (default: false) |

**Example:**
```python
get_manifest(project_path="/home/user/projects/myapi", quick=True)
```

### launch_claude_code

Launches a CLI agent in a visible terminal/GUI to execute a coding task. Returns a task ID for tracking.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `task` | string | Yes | Complete, detailed specification of what to build |
| `project_path` | string | Yes | Absolute path to the project directory |
| `cli` | string | No | Agent to use: `claude` (default), `gemini`, or `codex` |
| `model` | string | No | Model to use (agent-specific) |
| `additional_paths` | array | No | Additional project paths the agent can read from |
| `git_branch` | boolean | No | Create a safety branch before task (default: true) |

**Example:**
```python
launch_claude_code(
    task="Add user authentication with JWT tokens",
    project_path="/home/user/projects/myapi",
    cli="claude"
)
```

### get_task_result

Retrieves the result of a dispatched coding task including status, files modified, summary, and duration.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `task_id` | string | Yes | Task ID returned from launch_claude_code |

**Example:**
```python
get_task_result(task_id="abc123")
```

### list_recent_tasks

Lists recently dispatched tasks and their current status.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `limit` | integer | No | Max tasks to return (default: 5) |

**Example:**
```python
list_recent_tasks(limit=10)
```

### dispatch_assimilate

Starts a background process to analyze a codebase. Use for large projects where `get_manifest` might be slow. Returns immediately with a task ID.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `project_path` | string | Yes | Absolute path to project root |

**Example:**
```python
dispatch_assimilate(project_path="/home/user/projects/large-monorepo")
```

## License

MIT
