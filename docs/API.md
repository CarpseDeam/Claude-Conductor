# API Reference

## MCP Tools

### get_manifest

Get strategic overview of a codebase. Call this FIRST before coding tasks. Returns: project structure, stack detection (language/frameworks/tools), key files with parsed Python content including class names, method signatures, and function signatures. 

**Side Effects:** Generates or updates `.claude/steering.md` in the target project, which contains stack information and project-specific coding standards to guide agents.

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

Dispatch coding task to CLI agent. Auto-detects mode from content:
- **Spec mode**: Content starts with `## Spec:` → Two-phase execution: Phase 1 (Test Generation) followed by Phase 2 (Implementation).
- **Prose mode**: Direct execution for exploratory work, refactors, bug fixes.

Spec mode is preferred for new features with clear contracts.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `content` | string | Yes | Task content. Start with `## Spec:` for spec-driven mode. |
| `project_path` | string | Yes | Absolute path to project directory |
| `cli` | string | No | "claude", "gemini", or "codex" (default: "claude") |
| `model` | string | No | Model override |

**Returns:**
```json
{
  "status": "launched",
  "task_id": "a1b2c3d4",
  "mode": "spec",
  "cli": "Claude Code",
  "project_path": "C:\\Projects\\my-api",
  "message": "Spec-driven task launched. CLI will expand tests, implement, and validate."
}
```

---

### get_task_result

Get results of completed task.

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
