import sys
import time
from hashlib import md5
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import asyncio
import json
import subprocess
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from tasks.tracker import TaskTracker
from tasks.contracts import TaskStatus


class DispatchGuard:
    """Guards against duplicate and concurrent dispatches."""

    DEDUP_WINDOW = 300  # 5 minutes

    def __init__(self) -> None:
        self._recent_dispatches: dict[str, tuple[str, float]] = {}

    STALE_TASK_SECONDS = 600  # 10 minutes - tasks older than this are considered stale

    SESSION_MAX_AGE = 1800  # 30 minutes — sessions older than this are not routable

    def find_active_session(self, project_path: str, tracker: TaskTracker):
        """Find a running or completed task with an active session for this project.
        
        Returns the TaskRecord if a live session is available, None otherwise.
        Probes the socket before returning to confirm it's actually alive.
        """
        import time as _time
        from datetime import datetime
        now = datetime.now()
        pending_task = None

        for task in tracker.get_recent_tasks(10):
            if task.project_path != project_path:
                continue

            if task.status == TaskStatus.RUNNING:
                age = (now - task.started_at).total_seconds()
                if age > self.STALE_TASK_SECONDS:
                    task.status = TaskStatus.FAILED
                    task.error = "Stale task - auto-failed after 10 minutes"
                    task.socket_port = None
                    tracker._save(task)
                    continue
                if not task.socket_port and age < 10:
                    pending_task = task

            if not task.socket_port:
                continue

            # Skip old sessions — GUI was probably closed
            ref_time = task.completed_at or task.started_at
            if (now - ref_time).total_seconds() > self.SESSION_MAX_AGE:
                task.socket_port = None
                tracker._save(task)
                continue

            if task.status in (TaskStatus.RUNNING, TaskStatus.COMPLETED):
                return task

        # A task just launched but hasn't registered its port yet — wait for it
        if pending_task:
            for _ in range(8):
                _time.sleep(0.5)
                fresh = tracker.get_task(pending_task.task_id)
                if fresh and fresh.socket_port:
                    return fresh

        return None

    DISPATCH_WARN_THRESHOLD = 1500

    def check_length(self, content: str) -> str | None:
        """Return a warning if content is suspiciously long and not a Spec."""
        if len(content) >= self.DISPATCH_WARN_THRESHOLD and not content.lstrip().startswith("## Spec:"):
            return (
                f"Dispatch is {len(content)} chars — describe intent, not implementation. "
                "Pseudocode locks the CLI into your guess. Proceeding anyway."
            )
        return None

    def check_duplicate(self, content: str) -> dict | None:
        """Return blocking response if same content was recently dispatched."""
        content_hash = md5(content.encode()).hexdigest()[:12]
        now = time.time()

        self._recent_dispatches = {
            k: v for k, v in self._recent_dispatches.items()
            if now - v[1] < self.DEDUP_WINDOW
        }

        if content_hash in self._recent_dispatches:
            existing_id, _ = self._recent_dispatches[content_hash]
            return {
                "status": "duplicate",
                "task_id": existing_id,
                "message": "Same task already dispatched. Use get_task_result to check status."
            }
        return None

    def record_dispatch(self, content: str, task_id: str) -> None:
        """Record a dispatch for future deduplication."""
        content_hash = md5(content.encode()).hexdigest()[:12]
        self._recent_dispatches[content_hash] = (task_id, time.time())


SYSTEM_PROMPT = """## Code Standards

Write code that looks inevitable. Follow these constraints:

**Restraint**
- Solve it in one file if possible
- No abstractions until the third time you need them
- No classes if functions will do
- No inheritance - use composition

**Functions**
- Max 25 lines, aim for 15
- One level of nesting max
- Name describes exactly what it does: `extract_billable_hours()` not `process_data()`
- Input → transform → output. No side effects unless that's the point.

**Files**
- Max 200 lines for new files
- One clear responsibility
- If you're adding a second "system" to a file, stop and split

**No Ceremony**
- No AbstractFactory, no IServiceProvider, no Manager classes
- No code "just in case" - solve the actual problem
- Delete commented-out code, don't keep it

**Data**
- Use dataclasses or plain dicts, not classes with only __init__ and getters
- Data flows obviously - reader should predict what happens next
- No global state

**Treat the dispatch as intent, not a blueprint**
- If the dispatch contains pseudocode, class skeletons, or step-by-step control flow, treat these as hints about intent
- Read the actual source files and match existing patterns in this codebase
- Write idiomatic code — do not transliterate the dispatch

The best code is code you delete. Every line is a liability.
"""


class ClaudeCodeMCPServer:

    def __init__(self):
        self._server = Server("claude-code-bridge")
        self._dispatch_guard = DispatchGuard()
        self._register_handlers()

    def _register_handlers(self):
        self._server.list_tools()(self._list_tools)
        self._server.call_tool()(self._call_tool)

    async def _list_tools(self) -> list[Tool]:
        return [
            Tool(
                name="dispatch",
                description=(
                    "Dispatch a coding task to a CLI agent running in the project directory.\n\n"
                    "Describe INTENT and CONSTRAINTS, not implementation. The CLI reads the codebase "
                    "and writes the code. Pseudocode in dispatches is an anti-pattern — it creates "
                    "noise and locks the CLI into a guess instead of what the code actually needs.\n\n"
                    "BAD (pseudocode transliteration):\n"
                    "  'Create class FooHandler with method process(data: dict) -> Result. Inside, "
                    "check if data has id, loop through items calling bar_service.lookup(id), "
                    "accumulate into list, return Result...'\n\n"
                    "GOOD (intent + constraints):\n"
                    "  'Add FooHandler in src/handlers/foo_handler.py. Validates input has id, looks "
                    "up each item via bar_service, returns Result. Errors bubble.'\n\n"
                    "Use prose for bug fixes and small changes. Prefix with `## Spec:` for "
                    "non-trivial features that need structure. Include file paths and behavioral "
                    "requirements. Skip implementation details unless the exact change matters."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "Task description."
                        },
                        "project_path": {
                            "type": "string",
                            "description": "Absolute path to project directory"
                        },
                        "cli": {
                            "type": "string",
                            "enum": ["claude", "gemini", "codex"],
                            "description": "CLI to use (default: claude)"
                        },
                        "model": {
                            "type": "string",
                            "description": "Model to use (optional)"
                        }
                    },
                    "required": ["content", "project_path"]
                }
            ),
            Tool(
                name="get_task_result",
                description=(
                    "Get the result of a dispatched coding task. ONLY call this when user explicitly "
                    "says the task is done/finished/complete. NEVER call immediately after dispatch."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "task_id": {
                            "type": "string",
                            "description": "Task ID returned from dispatch"
                        }
                    },
                    "required": ["task_id"]
                }
            ),
            Tool(
                name="list_recent_tasks",
                description="List recently dispatched tasks and their status.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "description": "Max tasks to return (default: 5)"
                        }
                    }
                }
            ),
            Tool(
                name="health_check",
                description="Check server health status.",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            ),
        ]

    async def _call_tool(self, name: str, arguments: dict) -> list[TextContent]:
        if name == "dispatch":
            return self._handle_dispatch(arguments)
        elif name == "get_task_result":
            return self._handle_get_task_result(arguments)
        elif name == "list_recent_tasks":
            return self._handle_list_recent_tasks(arguments)
        elif name == "health_check":
            return self._handle_health_check(arguments)
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    def _handle_dispatch(self, arguments: dict) -> list[TextContent]:
        """Handle dispatch — routes to active session or launches new one."""
        content = arguments["content"]
        project_path = arguments["project_path"]
        cli = arguments.get("cli", "claude")
        model = arguments.get("model")

        if not Path(project_path).exists():
            return [TextContent(type="text", text=f"Path does not exist: {project_path}")]

        tracker = TaskTracker()

        # Try routing to an active session first
        active = self._dispatch_guard.find_active_session(project_path, tracker)
        if active and active.socket_port:
            result = self._try_session_send(active, content, tracker)
            if result:
                return result
            # Socket dead — fall through to fresh launch

        if blocking := self._dispatch_guard.check_duplicate(content):
            return [TextContent(type="text", text=json.dumps(blocking, indent=2))]

        return self._dispatch_new(content, project_path, cli, model, tracker)

    def _try_session_send(self, task, content: str, tracker: TaskTracker) -> list[TextContent] | None:
        """Try sending to an active session. Returns response on success, None if dead."""
        from gui.session import send_prompt

        if send_prompt(task.socket_port, content):
            return [TextContent(type="text", text=json.dumps({
                "status": "session_followup",
                "task_id": task.task_id,
                "session_id": task.session_id,
                "message": "Follow-up sent to active session. Output appears in the existing GUI window.",
            }, indent=2))]

        # Socket dead — clear port so we don't try again
        task.socket_port = None
        tracker._save(task)
        return None

    def _dispatch_new(self, content: str, project_path: str, cli: str,
                      model: str | None, tracker: TaskTracker) -> list[TextContent]:
        """Launch a new GUI viewer subprocess."""
        from dispatch import DispatchHandler

        handler = DispatchHandler()
        request = handler.prepare(content, Path(project_path), cli, model)
        full_prompt = handler.build_prompt(request, SYSTEM_PROMPT)

        task_id = tracker.create_task(project_path, cli)
        self._dispatch_guard.record_dispatch(content, task_id)
        length_warning = self._dispatch_guard.check_length(content)

        prompt_file = Path(project_path) / "_dispatch_prompt.txt"
        prompt_file.write_text(full_prompt, encoding='utf-8')

        viewer_script = Path(__file__).parent / "gui_viewer.py"
        venv_python = Path(__file__).parent.parent / ".venv" / "Scripts" / "python.exe"
        python_exe = str(venv_python) if venv_python.exists() else sys.executable

        cmd = [python_exe, str(viewer_script), project_path, str(prompt_file)]
        cmd.extend(["--task-id", task_id])
        cmd.extend(["--cli", cli])
        if model:
            cmd.extend(["--model", model])

        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )

        cli_names = {"claude": "Claude Code", "gemini": "Gemini CLI", "codex": "OpenAI Codex"}
        response: dict = {
            "status": "launched",
            "task_id": task_id,
            "cli": cli_names.get(cli, cli),
            "model": model or "default",
            "project_path": project_path,
            "message": "Task launched. DO NOT call get_task_result - wait for user to confirm completion.",
        }
        if length_warning is not None:
            response["dispatch_warning"] = length_warning
        return [TextContent(type="text", text=json.dumps(response, indent=2))]

    def _handle_get_task_result(self, arguments: dict) -> list[TextContent]:
        """Handle get_task_result tool call."""
        task_id = arguments["task_id"]
        tracker = TaskTracker()
        record = tracker.get_task(task_id)

        if not record:
            return [TextContent(type="text", text=f"Task not found: {task_id}")]

        duration = None
        if record.completed_at and record.started_at:
            duration = (record.completed_at - record.started_at).total_seconds()

        result = {
            "task_id": record.task_id,
            "status": record.status.value,
            "cli": record.cli,
            "project": record.project_path,
            "duration_seconds": duration,
            "files_modified": record.files_modified,
            "summary": record.summary,
            "error": record.error,
            "cli_output": record.cli_output,
        }
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    def _handle_list_recent_tasks(self, arguments: dict) -> list[TextContent]:
        """Handle list_recent_tasks tool call."""
        limit = arguments.get("limit", 5)
        tracker = TaskTracker()
        records = tracker.get_recent_tasks(limit)

        tasks = []
        for record in records:
            duration = None
            if record.completed_at and record.started_at:
                duration = (record.completed_at - record.started_at).total_seconds()
            tasks.append({
                "task_id": record.task_id,
                "status": record.status.value,
                "cli": record.cli,
                "project": Path(record.project_path).name,
                "started": record.started_at.isoformat(),
                "duration_seconds": duration,
            })

        return [TextContent(type="text", text=json.dumps(tasks, indent=2))]

    def _handle_health_check(self, arguments: dict) -> list[TextContent]:
        """Returns server status."""
        from datetime import datetime
        result = {
            "status": "ok",
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0"
        }
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def run(self):
        async with stdio_server() as (read_stream, write_stream):
            await self._server.run(read_stream, write_stream, self._server.create_initialization_options())


def main():
    server = ClaudeCodeMCPServer()
    asyncio.run(server.run())


if __name__ == "__main__":
    main()
