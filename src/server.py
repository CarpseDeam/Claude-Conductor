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

    def check_running_task(self, project_path: str, tracker: TaskTracker) -> dict | None:
        """Return blocking response if a task is already running for this project."""
        for task in tracker.get_recent_tasks(10):
            if task.project_path == project_path and task.status == TaskStatus.RUNNING:
                return {
                    "status": "already_running",
                    "task_id": task.task_id,
                    "message": "Task already running for this project. Use get_task_result to check status."
                }
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


SYSTEM_PROMPT = (
    "Write clean, scalable, modular, efficient code. "
    "Follow single responsibility principle. Do not repeat yourself. "
    "Use consistent naming conventions. No unnecessary comments."
)


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
                description=(
                    "Dispatch a coding task to CLI agent. Auto-detects mode from content:\n"
                    "- Spec mode: Content starts with '## Spec:' → expands tests, implements, validates\n"
                    "- Prose mode: Direct execution for exploratory work, refactors, bug fixes\n"
                    "Spec mode is preferred for new features with clear contracts."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "Task content. Start with '## Spec:' for spec-driven mode."
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
                    "Get the result of a dispatched coding task. Call this after user indicates "
                    "the task is finished. Returns: status, files modified, summary, duration."
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

        content = f"""# Project: {codebase_map.project_name}

## Stack
- Language: {stack.language}
- Frameworks: {frameworks}
- Tools: {tools}

## Code Standards
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
        steering_file = claude_dir / "steering.md"
        steering_file.write_text(content, encoding="utf-8")

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
        """Handle unified dispatch tool call."""
        from dispatch import DispatchHandler, DispatchMode

        content = arguments["content"]
        project_path = arguments["project_path"]
        cli = arguments.get("cli", "claude")
        model = arguments.get("model")

        if not Path(project_path).exists():
            return [TextContent(type="text", text=f"Path does not exist: {project_path}")]

        tracker = TaskTracker()

        if blocking := self._dispatch_guard.check_running_task(project_path, tracker):
            return [TextContent(type="text", text=json.dumps(blocking, indent=2))]

        if blocking := self._dispatch_guard.check_duplicate(content):
            return [TextContent(type="text", text=json.dumps(blocking, indent=2))]

        handler = DispatchHandler()
        try:
            request = handler.prepare(content, Path(project_path), cli, model)
        except ValueError as e:
            return [TextContent(type="text", text=f"Spec parse error: {e}")]

        full_prompt = handler.build_prompt(request, SYSTEM_PROMPT)

        task_id = tracker.create_task(project_path, cli)
        self._dispatch_guard.record_dispatch(content, task_id)

        if request.spec_name:
            record = tracker.get_task(task_id)
            if record:
                record.spec_name = request.spec_name
                tracker._save(record)

        prompt_file = Path(project_path) / "_dispatch_prompt.txt"
        prompt_file.write_text(full_prompt, encoding='utf-8')

        viewer_script = Path(__file__).parent / "gui_viewer.py"

        cmd = [sys.executable, str(viewer_script), project_path, str(prompt_file)]
        cmd.extend(["--task-id", task_id])
        cmd.extend(["--cli", cli])
        if model:
            cmd.extend(["--model", model])

        if request.mode == DispatchMode.SPEC:
            cmd.append("--spec-mode")
            test_path = handler.get_test_path(request)
            if test_path:
                cmd.extend(["--test-path", test_path])
                phase2_prompt = handler.build_phase2_prompt(request, test_path, SYSTEM_PROMPT)
                if phase2_prompt:
                    phase2_file = Path(project_path) / "_dispatch_prompt_phase2.txt"
                    phase2_file.write_text(phase2_prompt, encoding='utf-8')
                    cmd.extend(["--phase2-prompt", str(phase2_file)])

        subprocess.Popen(
            cmd,
            creationflags=subprocess.CREATE_NO_WINDOW,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL
        )

        cli_names = {"claude": "Claude Code", "gemini": "Gemini CLI", "codex": "OpenAI Codex"}
        response = {
            "status": "launched",
            "task_id": task_id,
            "mode": request.mode.value,
            "cli": cli_names.get(cli, cli),
            "model": model or "default",
            "project_path": project_path,
        }

        if request.spec_name:
            response["spec_name"] = request.spec_name

        response["message"] = (
            "Task launched. CLI executing in background. Check back with get_task_result(task_id) - do not dispatch again."
        )

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

    async def run(self):
        async with stdio_server() as (read_stream, write_stream):
            await self._server.run(read_stream, write_stream, self._server.create_initialization_options())


def main():
    server = ClaudeCodeMCPServer()
    asyncio.run(server.run())


if __name__ == "__main__":
    main()
