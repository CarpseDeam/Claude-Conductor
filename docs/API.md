# API Reference

## MCP Tools

### dispatch

Dispatch a coding task to a CLI agent running in the project directory.

**Intent over Implementation:**
Describe **INTENT** and **CONSTRAINTS**, not implementation details. The CLI reads the codebase and writes the code. Pseudocode in dispatches is discouraged as it often creates noise and locks the agent into suboptimal guesses.

**Persistent Sessions & Follow-ups:**
The server uses a `DispatchGuard` to manage project sessions:
1. **Session Routing**: If a task is already running or completed but the GUI window is still open for the given `project_path`, the server will automatically route the `content` as a follow-up turn to that window.
2. **Socket Probing**: The server probes the session socket to ensure it's alive before routing. Dead sessions (e.g. if the window was closed) trigger a fresh launch.
3. **Session Expiry**: Sessions are considered routable for up to 30 minutes after the last activity.
4. **Concurrency**: Only one active dispatch per project path is allowed. Tasks running longer than 10 minutes are auto-failed.

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
  "message": "Task launched. DO NOT call get_task_result - wait for user to confirm completion.",
  "dispatch_warning": "Dispatch is 1800 chars — describe intent, not implementation. Proceeding anyway."
}
```

**Returns (Session Follow-up):**
```json
{
  "status": "session_followup",
  "task_id": "a1b2c3d4",
  "message": "Follow-up sent to active session. Output appears in the existing GUI window."
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
