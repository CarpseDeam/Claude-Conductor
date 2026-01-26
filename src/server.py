import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import asyncio
import json
import subprocess
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent


SYSTEM_PROMPT = (
    "Write clean, scalable, modular, efficient code. "
    "Follow single responsibility principle. Do not repeat yourself. "
    "Use consistent naming conventions. No unnecessary comments."
)


class ClaudeCodeMCPServer:

    def __init__(self):
        self._server = Server("claude-code-bridge")
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
                    "Returns compressed project knowledge (~1-2K tokens). Cached after first run. "
                    "For large/unknown projects, use quick=true for fast initial scan, or "
                    "dispatch_assimilate for background full analysis."
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
                        },
                        "quick": {
                            "type": "boolean",
                            "description": "Fast shallow analysis (default: true). Set to false for full deep analysis."
                        }
                    },
                    "required": ["project_path"]
                }
            ),
            Tool(
                name="dispatch_assimilate",
                description=(
                    "Dispatch background codebase analysis. Returns immediately. "
                    "Use for large projects where get_manifest would be slow. "
                    "Check status with get_task_result or just call get_manifest after completion."
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
                name="launch_claude_code",
                description=(
                    "Launch Claude Code CLI in a visible terminal to execute a coding task. "
                    "Use this after gathering requirements from the user. "
                    "CRITICAL: project_path must be the EXACT absolute path to the project being discussed. "
                    "Do NOT guess - ask the user if unclear which project to work on."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "task": {
                            "type": "string",
                            "description": "Complete, detailed specification of what to build"
                        },
                        "project_path": {
                            "type": "string",
                            "description": "EXACT absolute path to the project directory (e.g. C:\\Projects\\MyProject). Ask user if unsure."
                        },
                        "additional_paths": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional additional project paths Claude can read from (e.g. related server/client projects)"
                        },
                        "cli": {
                            "type": "string",
                            "enum": ["claude", "gemini", "codex"],
                            "description": "Which CLI to use: claude (default), gemini, or codex"
                        },
                        "model": {
                            "type": "string",
                            "description": "Model to use"
                        },
                        "git_branch": {
                            "type": "boolean",
                            "description": "Create a safety branch before task (default: True)"
                        },
                        "godot_project": {
                            "type": "string",
                            "description": "Path to Godot project for validation"
                        }
                    },
                    "required": ["task", "project_path"]
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
                            "description": "Task ID returned from launch_claude_code"
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
        elif name == "launch_claude_code":
            return self._handle_launch_claude_code(arguments)
        elif name == "get_task_result":
            return self._handle_get_task_result(arguments)
        elif name == "list_recent_tasks":
            return self._handle_list_recent_tasks(arguments)
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    def _handle_get_manifest(self, arguments: dict) -> list[TextContent]:
        """Handle get_manifest tool call."""
        project_path = Path(arguments["project_path"])
        refresh = arguments.get("refresh", False)
        quick = arguments.get("quick", True)

        if not project_path.exists():
            return [TextContent(type="text", text=f"Path does not exist: {project_path}")]

        from assimilator.core import Assimilator
        from assimilator.output.cache import ManifestCache

        cache = ManifestCache()

        if not refresh:
            cached = cache.get_cached(project_path)
            if cached:
                return [TextContent(type="text", text=json.dumps(cached.to_compressed_dict(), indent=2))]

        assimilator = Assimilator(project_path)
        manifest = assimilator.assimilate(force_refresh=refresh, quick=quick)

        return [TextContent(type="text", text=json.dumps(manifest.to_compressed_dict(), indent=2))]

    def _handle_dispatch_assimilate(self, arguments: dict) -> list[TextContent]:
        """Handle dispatch_assimilate tool call - spawn background analysis."""
        project_path = Path(arguments["project_path"])

        if not project_path.exists():
            return [TextContent(type="text", text=f"Path does not exist: {project_path}")]

        from tasks.tracker import TaskTracker

        tracker = TaskTracker()
        task_id = tracker.create_task(str(project_path), cli="assimilator")

        script = Path(__file__).parent / "assimilator_runner.py"

        subprocess.Popen(
            [sys.executable, str(script), str(project_path), task_id],
            creationflags=subprocess.CREATE_NO_WINDOW,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )

        response = {
            "status": "dispatched",
            "task_id": task_id,
            "message": "Assimilation running in background. Call get_manifest(project_path) when ready."
        }
        return [TextContent(type="text", text=json.dumps(response, indent=2))]

    def _handle_launch_claude_code(self, arguments: dict) -> list[TextContent]:
        """Handle launch_claude_code tool call."""
        from tasks.tracker import TaskTracker

        task = arguments["task"]
        project_path = arguments["project_path"]
        additional_paths = arguments.get("additional_paths", [])
        cli = arguments.get("cli", "claude")
        model = arguments.get("model")
        godot_project = arguments.get("godot_project")

        if not Path(project_path).exists():
            return [TextContent(type="text", text=f"Path does not exist: {project_path}")]

        tracker = TaskTracker()
        task_id = tracker.create_task(project_path, cli)

        full_prompt = f"{task}\n\n{SYSTEM_PROMPT}"

        prompt_file = Path(project_path) / "_claude_prompt.txt"
        prompt_file.write_text(full_prompt, encoding='utf-8')

        viewer_script = Path(__file__).parent / "gui_viewer.py"
        python_exe = sys.executable

        cmd = [python_exe, str(viewer_script), project_path, str(prompt_file)]
        cmd.extend(["--task-id", task_id])
        for p in additional_paths:
            if Path(p).exists():
                cmd.extend(["--add-dir", p])
        cmd.extend(["--cli", cli])
        if model:
            cmd.extend(["--model", model])
        if godot_project:
            cmd.extend(["--godot-project", godot_project])

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
            "cli": cli_names.get(cli, cli),
            "model": model or "default",
            "project_path": project_path,
            "additional_paths": additional_paths,
            "message": "GUI window opened with live output. Use get_task_result with task_id when finished!"
        }
        return [TextContent(type="text", text=json.dumps(response, indent=2))]

    def _handle_get_task_result(self, arguments: dict) -> list[TextContent]:
        """Handle get_task_result tool call."""
        from tasks.tracker import TaskTracker

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
        }
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    def _handle_list_recent_tasks(self, arguments: dict) -> list[TextContent]:
        """Handle list_recent_tasks tool call."""
        from tasks.tracker import TaskTracker

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
