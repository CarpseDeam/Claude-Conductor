import sys
import re
import os
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

# ---------------------------------------------------------------------------
# Dispatch imports — kept for when dispatch tools are re-enabled
# ---------------------------------------------------------------------------
# from tasks.tracker import TaskTracker
# from tasks.contracts import TaskStatus

# ---------------------------------------------------------------------------
# Noise directories skipped by structure/search tools
# ---------------------------------------------------------------------------
_SKIP_DIRS = {
    ".venv", "venv", "__pycache__", ".git", "node_modules",
    ".mypy_cache", ".pytest_cache", "dist", "build", ".idea", ".vs",
}

_READ_LINE_LIMIT = 250   # max lines returned by read_file by default
_READ_LINE_LIMIT_MAX = 2000
_BINARY_SAMPLE_SIZE = 4096
_SEARCH_MATCH_LIMIT = 30  # max matches returned by search_files
_LINE_TRUNCATE = 200      # chars per line before truncation in search results
_DIR_ENTRY_LIMIT = 150    # max entries in list_directory


# ---------------------------------------------------------------------------
# Dispatch guard — kept for when dispatch tools are re-enabled
# ---------------------------------------------------------------------------
class DispatchGuard:
    """Guards against duplicate and concurrent dispatches."""

    DEDUP_WINDOW = 300

    def __init__(self) -> None:
        self._recent_dispatches: dict[str, tuple[str, float]] = {}

    STALE_TASK_SECONDS = 600
    SESSION_MAX_AGE = 1800

    def find_active_session(self, project_path: str, tracker):
        import time as _time
        from datetime import datetime
        now = datetime.now()
        pending_task = None

        for task in tracker.get_recent_tasks(10):
            if task.project_path != project_path:
                continue
            # (status checks omitted — re-enable with TaskStatus import)
            if not task.socket_port:
                continue
            ref_time = task.completed_at or task.started_at
            if (now - ref_time).total_seconds() > self.SESSION_MAX_AGE:
                task.socket_port = None
                tracker._save(task)
                continue
            return task

        if pending_task:
            for _ in range(8):
                _time.sleep(0.5)
                fresh = tracker.get_task(pending_task.task_id)
                if fresh and fresh.socket_port:
                    return fresh
        return None

    def check_duplicate(self, content: str) -> dict | None:
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
                "message": "Same task already dispatched. Use get_task_result to check status.",
            }
        return None

    def record_dispatch(self, content: str, task_id: str) -> None:
        content_hash = md5(content.encode()).hexdigest()[:12]
        self._recent_dispatches[content_hash] = (task_id, time.time())


SYSTEM_PROMPT = """Make the change described. The dispatch names the files that matter — work those, then stop. Match existing style; type hints everywhere."""


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
            # ---------------------------------------------------------------
            # File explorer tools (active)
            # ---------------------------------------------------------------
            Tool(
                name="read_file",
                description=(
                    "Read a file from a project. Returns up to `limit` lines starting at `offset`. "
                    "Use offset+limit to page through large files rather than reading everything at once."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Absolute path to file"},
                        "offset": {"type": "integer", "description": "Line to start from (0-based, default 0)"},
                        "start_line": {"type": "integer", "description": "Line to start from (1-based; overrides offset)"},
                        "limit": {
                            "type": "integer",
                            "description": (
                                f"Max lines to return (default {_READ_LINE_LIMIT}, "
                                f"max {_READ_LINE_LIMIT_MAX})"
                            ),
                        },
                    },
                    "required": ["path"],
                },
            ),
            Tool(
                name="list_directory",
                description=(
                    "List files and directories at a path. Skips noise dirs (.venv, __pycache__, node_modules, etc.). "
                    "Set recursive=true to walk the whole tree (capped at 150 entries)."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Absolute path to directory"},
                        "recursive": {"type": "boolean", "description": "Walk subdirectories (default false)"},
                    },
                    "required": ["path"],
                },
            ),
            Tool(
                name="search_files",
                description=(
                    "Regex search across files in a directory. Returns up to 30 matches with file path and line number. "
                    "Use glob to narrow scope (e.g. '*.py'). Skips noise dirs."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Root directory to search"},
                        "pattern": {"type": "string", "description": "Regex pattern"},
                        "glob": {"type": "string", "description": "File glob filter (e.g. '*.py', default '*')"},
                        "case_sensitive": {"type": "boolean", "description": "Default false"},
                    },
                    "required": ["path", "pattern"],
                },
            ),
            Tool(
                name="get_project_structure",
                description=(
                    "Return a directory tree for a project (max depth 4). "
                    "Skips noise dirs. Good for understanding layout before planning."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Absolute path to project root"},
                        "max_depth": {"type": "integer", "description": "Max depth (default 4)"},
                    },
                    "required": ["path"],
                },
            ),
            # ---------------------------------------------------------------
            # Dispatch tools — disabled, re-enable by uncommenting below
            # ---------------------------------------------------------------
            # Tool(
            #     name="dispatch",
            #     description=(
            #         "Send a coding task to a CLI agent in the project directory."
            #     ),
            #     inputSchema={
            #         "type": "object",
            #         "properties": {
            #             "content": {"type": "string"},
            #             "project_path": {"type": "string"},
            #             "cli": {"type": "string", "enum": ["claude", "gemini", "codex"]},
            #             "model": {"type": "string"},
            #         },
            #         "required": ["content", "project_path"],
            #     },
            # ),
            # Tool(
            #     name="get_task_result",
            #     description="Get the result of a dispatched coding task.",
            #     inputSchema={
            #         "type": "object",
            #         "properties": {"task_id": {"type": "string"}},
            #         "required": ["task_id"],
            #     },
            # ),
            # Tool(
            #     name="list_recent_tasks",
            #     description="List recently dispatched tasks and their status.",
            #     inputSchema={
            #         "type": "object",
            #         "properties": {"limit": {"type": "integer"}},
            #     },
            # ),
        ]

    async def _call_tool(self, name: str, arguments: dict) -> list[TextContent]:
        if name == "read_file":
            return self._handle_read_file(arguments)
        elif name == "list_directory":
            return self._handle_list_directory(arguments)
        elif name == "search_files":
            return self._handle_search_files(arguments)
        elif name == "get_project_structure":
            return self._handle_get_project_structure(arguments)
        # Dispatch tools — re-enable alongside Tool definitions above
        # elif name == "dispatch":
        #     return self._handle_dispatch(arguments)
        # elif name == "get_task_result":
        #     return self._handle_get_task_result(arguments)
        # elif name == "list_recent_tasks":
        #     return self._handle_list_recent_tasks(arguments)
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    # -----------------------------------------------------------------------
    # File explorer handlers
    # -----------------------------------------------------------------------

    def _handle_read_file(self, arguments: dict) -> list[TextContent]:
        path = self._resolve_user_path(arguments["path"])
        offset_error, offset = self._read_offset(arguments)
        if offset_error:
            return [TextContent(type="text", text=offset_error)]
        limit_error, limit = self._read_limit(arguments)
        if limit_error:
            return [TextContent(type="text", text=limit_error)]

        if not path.exists():
            return [TextContent(type="text", text=f"File not found: {path}")]
        if not path.is_file():
            return [TextContent(type="text", text=f"Not a file: {path}")]
        if self._is_probably_binary(path):
            return [TextContent(type="text", text=f"Binary file not displayed: {path}")]

        try:
            chunk, next_offset, total = self._read_line_window(path, offset, limit)
        except Exception as e:
            return [TextContent(type="text", text=f"Error reading file: {e}")]

        if not chunk and total <= offset:
            return [TextContent(type="text", text=f"# {path}\n\nNo lines at offset {offset}. File has {total} line(s).")]

        end_line = offset + len(chunk)
        header = f"# {path}  (lines {offset + 1}-{end_line}"
        if total > next_offset:
            header += f", at least {next_offset + 1}; use offset={next_offset} for more)"
        else:
            header += f" of {total})"

        body = "\n".join(f"{offset + i + 1:>4}  {line}" for i, line in enumerate(chunk))
        return [TextContent(type="text", text=f"{header}\n\n{body}")]

    def _handle_list_directory(self, arguments: dict) -> list[TextContent]:
        root = self._resolve_user_path(arguments["path"])
        recursive = bool(arguments.get("recursive", False))

        if not root.exists():
            return [TextContent(type="text", text=f"Path not found: {root}")]
        if not root.is_dir():
            return [TextContent(type="text", text=f"Not a directory: {root}")]

        entries: list[str] = []
        count = 0

        def _walk(p: Path, depth: int):
            nonlocal count
            try:
                children = sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
            except PermissionError:
                return
            for child in children:
                if count >= _DIR_ENTRY_LIMIT:
                    entries.append(f"  ... (capped at {_DIR_ENTRY_LIMIT} entries)")
                    return
                if child.is_dir() and child.name in _SKIP_DIRS:
                    continue
                rel = child.relative_to(root)
                prefix = "  " * depth
                if child.is_dir():
                    entries.append(f"{prefix}{rel}/")
                    if recursive:
                        _walk(child, depth + 1)
                else:
                    try:
                        size = child.stat().st_size
                        size_str = f"  ({size:,} B)" if size < 100_000 else f"  ({size / 1024:.0f} KB)"
                    except OSError:
                        size_str = ""
                    entries.append(f"{prefix}{rel}{size_str}")
                count += 1

        _walk(root, 0)
        text = f"# {root}\n\n" + "\n".join(entries)
        return [TextContent(type="text", text=text)]

    def _handle_search_files(self, arguments: dict) -> list[TextContent]:
        root = self._resolve_user_path(arguments["path"])
        pattern = arguments["pattern"]
        glob_filter = arguments.get("glob", "*")
        case_sensitive = bool(arguments.get("case_sensitive", False))

        if not root.exists():
            return [TextContent(type="text", text=f"Path not found: {root}")]

        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            rx = re.compile(pattern, flags)
        except re.error as e:
            return [TextContent(type="text", text=f"Invalid regex: {e}")]

        matches: list[str] = []
        total_matches = 0

        for file in sorted(root.rglob(glob_filter)):
            if not file.is_file():
                continue
            if any(part in _SKIP_DIRS for part in file.parts):
                continue
            if self._is_probably_binary(file):
                continue
            try:
                for lineno, line in self._iter_text_lines(file):
                    if rx.search(line):
                        total_matches += 1
                        if len(matches) < _SEARCH_MATCH_LIMIT:
                            display = line[:_LINE_TRUNCATE] + ("..." if len(line) > _LINE_TRUNCATE else "")
                            rel = file.relative_to(root)
                            matches.append(f"{rel}:{lineno}: {display}")
            except Exception:
                continue

        if not matches:
            return [TextContent(type="text", text=f"No matches for `{pattern}` in {root}")]

        header = f"# {total_matches} match(es) for `{pattern}` in {root}"
        if total_matches > _SEARCH_MATCH_LIMIT:
            header += f"  [showing first {_SEARCH_MATCH_LIMIT}]"
        return [TextContent(type="text", text=header + "\n\n" + "\n".join(matches))]

    def _handle_get_project_structure(self, arguments: dict) -> list[TextContent]:
        root = self._resolve_user_path(arguments["path"])
        max_depth = int(arguments.get("max_depth", 4))

        if not root.exists():
            return [TextContent(type="text", text=f"Path not found: {root}")]

        lines: list[str] = [str(root)]

        def _tree(p: Path, depth: int, prefix: str):
            if depth > max_depth:
                return
            try:
                children = sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
            except PermissionError:
                return
            children = [c for c in children if not (c.is_dir() and c.name in _SKIP_DIRS)]
            for i, child in enumerate(children):
                connector = "└── " if i == len(children) - 1 else "├── "
                lines.append(f"{prefix}{connector}{child.name}{'/' if child.is_dir() else ''}")
                if child.is_dir():
                    extension = "    " if i == len(children) - 1 else "│   "
                    _tree(child, depth + 1, prefix + extension)

        _tree(root, 1, "")
        return [TextContent(type="text", text="\n".join(lines))]

    def _resolve_user_path(self, raw_path: str) -> Path:
        expanded = os.path.expandvars(str(raw_path))
        expanded = re.sub(
            r"%([^%]+)%",
            lambda match: os.environ.get(match.group(1), match.group(0)),
            expanded,
        )
        return Path(expanded).expanduser()

    def _read_offset(self, arguments: dict) -> tuple[str | None, int]:
        if "start_line" in arguments and arguments.get("start_line") is not None:
            try:
                start_line = int(arguments["start_line"])
            except (TypeError, ValueError):
                return "Invalid start_line: expected an integer", 0
            if start_line < 1:
                return "Invalid start_line: must be >= 1", 0
            return None, start_line - 1

        raw_offset = arguments.get("offset", 0)
        if raw_offset is None:
            raw_offset = 0
        try:
            offset = int(raw_offset)
        except (TypeError, ValueError):
            return "Invalid offset: expected an integer", 0
        if offset < 0:
            return "Invalid offset: must be >= 0", 0
        return None, offset

    def _read_limit(self, arguments: dict) -> tuple[str | None, int]:
        raw_limit = arguments.get("limit", _READ_LINE_LIMIT)
        if raw_limit is None:
            raw_limit = _READ_LINE_LIMIT
        try:
            limit = int(raw_limit)
        except (TypeError, ValueError):
            return "Invalid limit: expected an integer", _READ_LINE_LIMIT
        if limit < 1:
            return "Invalid limit: must be >= 1", _READ_LINE_LIMIT
        return None, min(limit, _READ_LINE_LIMIT_MAX)

    def _read_line_window(self, path: Path, offset: int, limit: int) -> tuple[list[str], int, int]:
        lines: list[str] = []
        next_offset = offset
        total = 0
        stop_after = offset + limit

        with path.open("r", encoding="utf-8", errors="replace", newline=None) as handle:
            for total, line in enumerate(handle, 1):
                if total <= offset:
                    continue
                if total <= stop_after:
                    lines.append(line.rstrip("\r\n"))
                    next_offset = total
                    continue
                return lines, stop_after, total

        return lines, next_offset, total

    def _iter_text_lines(self, path: Path):
        with path.open("r", encoding="utf-8", errors="replace", newline=None) as handle:
            for lineno, line in enumerate(handle, 1):
                yield lineno, line.rstrip("\r\n")

    def _is_probably_binary(self, path: Path) -> bool:
        try:
            with path.open("rb") as handle:
                sample = handle.read(_BINARY_SAMPLE_SIZE)
        except OSError:
            return False
        if b"\x00" in sample:
            return True
        return False

    # -----------------------------------------------------------------------
    # Dispatch handlers — kept, re-enable by uncommenting in _call_tool above
    # -----------------------------------------------------------------------

    def _handle_dispatch(self, arguments: dict) -> list[TextContent]:
        content = arguments["content"]
        project_path = arguments["project_path"]
        cli = arguments.get("cli", "claude")
        model = arguments.get("model")

        if not Path(project_path).exists():
            return [TextContent(type="text", text=f"Path does not exist: {project_path}")]

        from tasks.tracker import TaskTracker
        tracker = TaskTracker()

        active = self._dispatch_guard.find_active_session(project_path, tracker)
        if active and active.socket_port:
            result = self._try_session_send(active, content, tracker)
            if result:
                return result

        if blocking := self._dispatch_guard.check_duplicate(content):
            return [TextContent(type="text", text=json.dumps(blocking, indent=2))]

        return self._dispatch_new(content, project_path, cli, model, tracker)

    def _try_session_send(self, task, content: str, tracker) -> list[TextContent] | None:
        from gui.session import send_prompt
        if send_prompt(task.socket_port, content):
            return [TextContent(type="text", text=json.dumps({
                "status": "session_followup",
                "task_id": task.task_id,
                "session_id": task.session_id,
                "message": "Follow-up sent to active session. Output appears in the existing GUI window.",
            }, indent=2))]
        task.socket_port = None
        tracker._save(task)
        return None

    def _dispatch_new(self, content: str, project_path: str, cli: str,
                      model: str | None, tracker) -> list[TextContent]:
        from dispatch import DispatchHandler
        handler = DispatchHandler()
        request = handler.prepare(content, Path(project_path), cli, model)
        full_prompt = handler.build_prompt(request, SYSTEM_PROMPT)

        task_id = tracker.create_task(project_path, cli)
        self._dispatch_guard.record_dispatch(content, task_id)

        prompt_file = Path(project_path) / "_dispatch_prompt.txt"
        prompt_file.write_text(full_prompt, encoding="utf-8")

        viewer_script = Path(__file__).parent / "gui_viewer.py"
        venv_python = Path(__file__).parent.parent / ".venv" / "Scripts" / "python.exe"
        python_exe = str(venv_python) if venv_python.exists() else sys.executable

        cmd = [python_exe, str(viewer_script), project_path, str(prompt_file),
               "--task-id", task_id, "--cli", cli]
        if model:
            cmd.extend(["--model", model])

        subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)

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
        from tasks.tracker import TaskTracker
        task_id = arguments["task_id"]
        tracker = TaskTracker()
        record = tracker.get_task(task_id)
        if not record:
            return [TextContent(type="text", text=f"Task not found: {task_id}")]
        duration = None
        if record.completed_at and record.started_at:
            duration = (record.completed_at - record.started_at).total_seconds()
        return [TextContent(type="text", text=json.dumps({
            "task_id": record.task_id,
            "status": record.status.value,
            "cli": record.cli,
            "project": record.project_path,
            "duration_seconds": duration,
            "files_modified": record.files_modified,
            "summary": record.summary,
            "error": record.error,
            "cli_output": record.cli_output,
        }, indent=2))]

    def _handle_list_recent_tasks(self, arguments: dict) -> list[TextContent]:
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
            await self._server.run(
                read_stream, write_stream,
                self._server.create_initialization_options(),
            )


def main():
    server = ClaudeCodeMCPServer()
    asyncio.run(server.run())


if __name__ == "__main__":
    main()
