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

    def find_active_session(self, project_path: str, tracker: TaskTracker):
        """Find a running or completed task with an active session for this project.
        
        Returns the TaskRecord if a session is available, None otherwise.
        Also cleans up stale tasks.
        """
        from datetime import datetime
        from tasks.contracts import TaskRecord
        now = datetime.now()
        for task in tracker.get_recent_tasks(10):
            if task.project_path != project_path:
                continue
            if task.status == TaskStatus.RUNNING:
                age = (now - task.started_at).total_seconds()
                if age > self.STALE_TASK_SECONDS:
                    task.status = TaskStatus.FAILED
                    task.error = "Stale task - auto-failed after 10 minutes"
                    tracker._save(task)
                    continue
            if task.socket_port and task.status in (TaskStatus.RUNNING, TaskStatus.COMPLETED):
                return task
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
                name="get_manifest",
                description=(
                    "Get strategic overview of a codebase. Call this FIRST before coding tasks. "
                    "Returns: project structure, stack detection (language/frameworks/tools), "
                    "key files with AST-parsed method signatures. Fast (<1s) - no git calls. "
                    "Cached to docs/STRUCT.md; use refresh=true to regenerate after changes."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "project_path": {
                            "type": "string",
                            "description": "Absolute path to project root (e.g. C:\\Projects\\MyApp)"
                        },
                        "refresh": {
                            "type": "boolean",
                            "description": "Force rebuild manifest, ignore cache (default: false)"
                        }
                    },
                    "required": ["project_path"]
                }
            ),
            Tool(
                name="dispatch_assimilate",
                description=(
                    "[DEPRECATED] Use get_manifest instead - it's now fast enough for synchronous use."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "project_path": {
                            "type": "string",
                            "description": "Absolute path to project root"
                        }
                    },
                    "required": ["project_path"]
                }
            ),
            Tool(
                name="dispatch",
                description="Dispatch a coding task to CLI agent. Describe what you want done.",
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
        if name == "get_manifest":
            return self._handle_get_manifest(arguments)
        elif name == "dispatch_assimilate":
            return self._handle_dispatch_assimilate(arguments)
        elif name == "dispatch":
            return self._handle_dispatch(arguments)
        elif name == "get_task_result":
            return self._handle_get_task_result(arguments)
        elif name == "list_recent_tasks":
            return self._handle_list_recent_tasks(arguments)
        elif name == "health_check":
            return self._handle_health_check(arguments)
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    def _handle_get_manifest(self, arguments: dict) -> list[TextContent]:
        """Handle get_manifest tool call."""
        from mapper import CodebaseMapper

        project_path = Path(arguments["project_path"])
        refresh = arguments.get("refresh", False)

        if not project_path.exists():
            return [TextContent(type="text", text=f"Path does not exist: {project_path}")]

        struct_md = project_path / "docs" / "STRUCT.md"

        if struct_md.exists() and not refresh:
            return [TextContent(type="text", text=struct_md.read_text(encoding="utf-8"))]

        mapper = CodebaseMapper(project_path)
        codebase_map = mapper.map()
        markdown = codebase_map.to_markdown()

        (project_path / "docs").mkdir(exist_ok=True)
        struct_md.write_text(markdown, encoding="utf-8")

        self._generate_steering_file(project_path, codebase_map)

        return [TextContent(type="text", text=markdown)]

    def _generate_steering_file(self, project_path: Path, codebase_map) -> None:
        """Generate .claude/steering.md with project standards."""
        claude_dir = project_path / ".claude"
        claude_dir.mkdir(exist_ok=True)

        stack = codebase_map.stack
        frameworks = ", ".join(stack.frameworks) if stack.frameworks else "None"
        tools = ", ".join(stack.tools) if stack.tools else "None"

        if stack.language == "gdscript":
            content = self._generate_godot_steering(codebase_map, stack, frameworks, tools, project_path)
        else:
            content = self._generate_python_steering(codebase_map, stack, frameworks, tools, project_path)

        steering_file = claude_dir / "steering.md"
        steering_file.write_text(content, encoding="utf-8")

    def _generate_godot_steering(self, codebase_map, stack, frameworks: str, tools: str, project_path: Path) -> str:
        """Generate steering file content for Godot projects."""
        gut_addon = project_path / "addons" / "gut"
        gut_note = ""
        if not gut_addon.exists():
            gut_note = "\n- NOTE: GUT addon not found. Install from AssetLib or https://github.com/bitwes/Gut"

        return f"""# Project: {codebase_map.project_name}

## Stack
- Language: {stack.language}
- Frameworks: {frameworks}
- Tools: {tools}

## Environment
- Engine: Godot 4.x
- Test framework: GUT (Godot Unit Test)
- Run tests: `godot --headless -s addons/gut/gut_cmdline.gd -gdir=res://tests/ -gexit`{gut_note}

## Code Standards
- New files: aim 200-300 lines, split at 400
- Existing files: don't refactor unless >500 lines
- Max function size: 25 lines (40+ ok if one clear purpose)
- Use static typing (var x: int, func foo() -> void)
- Use class_name for reusable classes
- Use signals for decoupled communication

## Testing
- GUT for all tests
- Test file mirrors source: scripts/player.gd → tests/test_player.gd
- Test files: res://tests/test_*.gd
"""

    def _generate_python_steering(self, codebase_map, stack, frameworks: str, tools: str, project_path: Path) -> str:
        """Generate steering file content for Python projects."""
        venv_section = ""
        venv_path = project_path / ".venv"
        if venv_path.exists():
            if (venv_path / "Scripts").exists():  # Windows
                venv_section = """## Environment
- Virtual env: `.venv` (Windows)
- Python: `.venv/Scripts/python.exe`
- Run tests: `.venv/Scripts/python.exe -m pytest tests/ -v`
- Install deps: `.venv/Scripts/pip.exe install <pkg>`
"""
            else:  # Unix
                venv_section = """## Environment
- Virtual env: `.venv`
- Python: `.venv/bin/python`
- Run tests: `.venv/bin/python -m pytest tests/ -v`
- Install deps: `.venv/bin/pip install <pkg>`
"""

        return f"""# Project: {codebase_map.project_name}

## Stack
- Language: {stack.language}
- Frameworks: {frameworks}
- Tools: {tools}

{venv_section}## Code Standards
- New files: aim 200-300 lines, split at 400
- Existing files: don't refactor unless >500 lines
- Working god files: leave alone (one responsibility > line count)
- Max function size: 25 lines (40+ ok if one clear purpose)
- Full type hints required
- Use dataclasses/pydantic for structured data
- pathlib over os.path

## Testing
- pytest for all tests
- No mocks unless external service
- Test file mirrors source: src/foo.py → tests/test_foo.py
"""

    def _handle_dispatch_assimilate(self, arguments: dict) -> list[TextContent]:
        """Handle dispatch_assimilate tool call - deprecated."""
        return [TextContent(
            type="text",
            text=(
                "dispatch_assimilate is deprecated. "
                "Use get_manifest instead - it's now fast enough (<2s) for synchronous use."
            )
        )]

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
            return self._dispatch_to_session(active, content, project_path)

        if blocking := self._dispatch_guard.check_duplicate(content):
            return [TextContent(type="text", text=json.dumps(blocking, indent=2))]

        return self._dispatch_new(content, project_path, cli, model, tracker)

    def _dispatch_to_session(self, task, content: str, project_path: str) -> list[TextContent]:
        """Send a follow-up prompt to an existing GUI session via socket."""
        from gui.session import send_prompt

        success = send_prompt(task.socket_port, content)
        if success:
            return [TextContent(type="text", text=json.dumps({
                "status": "session_followup",
                "task_id": task.task_id,
                "session_id": task.session_id,
                "message": "Follow-up sent to active session. Output appears in the existing GUI window.",
            }, indent=2))]

        # Socket dead — session closed. Clear port and fall through to new launch.
        task.socket_port = None
        TaskTracker()._save(task)
        return [TextContent(type="text", text=json.dumps({
            "status": "session_expired",
            "message": "Previous session closed. Dispatch again to start a new session.",
        }, indent=2))]

    def _dispatch_new(self, content: str, project_path: str, cli: str,
                      model: str | None, tracker: TaskTracker) -> list[TextContent]:
        """Launch a new GUI viewer subprocess."""
        from dispatch import DispatchHandler

        handler = DispatchHandler()
        request = handler.prepare(content, Path(project_path), cli, model)
        full_prompt = handler.build_prompt(request, SYSTEM_PROMPT)

        task_id = tracker.create_task(project_path, cli)
        self._dispatch_guard.record_dispatch(content, task_id)

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
        return [TextContent(type="text", text=json.dumps({
            "status": "launched",
            "task_id": task_id,
            "cli": cli_names.get(cli, cli),
            "model": model or "default",
            "project_path": project_path,
            "message": "Task launched. DO NOT call get_task_result - wait for user to confirm completion.",
        }, indent=2))]

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
