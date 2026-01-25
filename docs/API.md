# API Reference

## MCP Tools

### get_manifest

Get compressed codebase knowledge. Call FIRST before coding tasks.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `project_path` | string | Yes | Absolute path to project root |
| `refresh` | boolean | No | Force rebuild, ignore cache |
| `quick` | boolean | No | Fast shallow analysis |

**Returns:**
```json
{
  "project": "my-api",
  "lang": "python",
  "stack": ["FastAPI", "SQLAlchemy"],
  "structure": {"src/api/": "Route handlers"},
  "components": [...],
  "patterns": {"auth": "JWT via python-jose"},
  "stats": {"files": 42, "lines": 3500}
}
```

---

### launch_claude_code

Dispatch coding task to CLI agent. Returns immediately.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `project_path` | string | Yes | Absolute path to project |
| `task` | string | Yes | Detailed task specification |
| `cli` | string | No | "claude", "gemini", or "codex" (default: "claude") |
| `model` | string | No | Model override |
| `additional_paths` | array | No | Extra directories agent can read |
| `git_branch` | boolean | No | Create safety branch (default: true) |
| `godot_project` | string | No | Path for Godot validation |

**Returns:**
```json
{
  "status": "launched",
  "task_id": "a1b2c3d4",
  "cli": "Claude Code",
  "project_path": "C:\\Projects\\my-api"
}
```

---

### get_task_result

Get results of completed task.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `task_id` | string | Yes | Task ID from launch_claude_code |

**Returns:**
```json
{
  "task_id": "a1b2c3d4",
  "status": "completed",
  "duration_seconds": 180,
  "files_modified": ["src/auth.py", "tests/test_auth.py"],
  "summary": "Added password reset with email verification"
}
```

---

### list_recent_tasks

List recently dispatched tasks.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `limit` | integer | No | Max results (default: 5) |

**Returns:**
```json
{
  "tasks": [
    {"task_id": "a1b2c3d4", "status": "completed", "cli": "claude"},
    {"task_id": "e5f6g7h8", "status": "running", "cli": "gemini"}
  ]
}
```

---

### dispatch_assimilate

Background codebase analysis. Non-blocking.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `project_path` | string | Yes | Absolute path to project |

**Returns:**
```json
{
  "status": "dispatched",
  "task_id": "x9y0z1a2",
  "message": "Assimilation running. Call get_manifest when ready."
}
```
