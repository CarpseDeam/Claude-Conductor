# API Reference

## MCP Tools

### get_manifest

Get strategic overview of a codebase. Call this FIRST before coding tasks. Returns: project structure, stack detection (language/frameworks/tools), key files with parsed content. 

**Side Effects:** Generates or updates `.claude/steering.md` in the target project, which contains stack information and project-specific coding standards to guide agents. Supports both Python and Godot (GDScript) environments.

Helps understand where code lives and what interfaces exist. Cached to docs/STRUCT.md; use refresh=true to regenerate after changes.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `project_path` | string | Yes | Absolute path to project root |
| `refresh` | boolean | No | Force rebuild, ignore cache |

**Returns:**
```markdown
# project-name

**Language:** python
**Frameworks:** FastAPI, Pydantic

## Structure
- `src/` - Source code (12 files)
- `tests/` - Tests (5 files)

## Key Files
- `src/main.py` - Entry point
- `src/models.py` - Data models

## Module Details
### `src/models.py`
_Data models for the user service._

**User**: `__init__(name, email)`, `to_dict() -> dict`

**Functions**: `validate_email(email) -> bool`

## Dependencies
- `src/main.py` -> src.models, src.utils
- `src/models.py` -> pydantic

## Stats
- Files: 17
- Directories: 3
- Lines: 1250
```

---

### dispatch

Dispatch coding task to CLI agent. Describe what you want done in the content parameter.

**Persistent Sessions & Follow-ups:**
The server uses a `DispatchGuard` to manage project sessions:
1. **Session Routing**: If a task is already running or completed but the GUI window is still open for the given `project_path`, the server will automatically route the `content` as a follow-up turn to that window. This avoids launching multiple windows for the same project.
2. **Claude Resume**: For Claude CLI, the server captures the `session_id` from the first turn and uses `--resume` for subsequent turns in the same window.
3. **Concurrency**: Only one active dispatch per project path is allowed. Tasks running longer than 10 minutes are auto-failed.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `content` | string | Yes | Task description. |
| `project_path` | string | Yes | Absolute path to project directory |
| `cli` | string | No | "claude", "gemini", or "codex" (default: "claude") |
| `model` | string | No | Model override |

**Returns (New Launch):**
```json
{
  "status": "launched",
  "task_id": "a1b2c3d4",
  "cli": "Claude Code",
  "project_path": "C:\\Projects\\my-api",
  "message": "Task launched. DO NOT call get_task_result - wait for user to confirm completion."
}
```

**Returns (Session Follow-up):**
```json
{
  "status": "session_followup",
  "task_id": "a1b2c3d4",
  "session_id": "s12345",
  "message": "Follow-up sent to active session. Output appears in the existing GUI window."
}
```

**Error Responses:**
```json
{
  "status": "session_expired",
  "message": "Previous session closed. Dispatch again to start a new session."
}
```
or
```json
{
  "status": "duplicate",
  "task_id": "existing_id",
  "message": "Same task already dispatched. Use get_task_result to check status."
}
```

---

### get_task_result

Get the result of a dispatched coding task. ONLY call this when user explicitly says the task is done/finished/complete. NEVER call immediately after dispatch.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `task_id` | string | Yes | Task ID returned from `dispatch` |

**Returns:**
```json
{
  "task_id": "a1b2c3d4",
  "status": "completed",
  "duration_seconds": 180,
  "files_modified": ["src/auth.py", "tests/test_auth.py"],
  "summary": "Added password reset with email verification",
  "cli_output": "... full agent output ..."
}
```
or (on failure):
```json
{
  "task_id": "a1b2c3d4",
  "status": "failed",
  "error": "Window closed before completion",
  "duration_seconds": 45
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

### health_check

Check server health status.

**Returns:**
```json
{
  "status": "ok",
  "timestamp": "2026-01-26T12:00:00Z",
  "version": "1.0.0"
}
```

---

### dispatch_assimilate [DEPRECATED]

**Note: This tool is deprecated. Use `get_manifest` instead, which is now fast enough for synchronous use.**

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
