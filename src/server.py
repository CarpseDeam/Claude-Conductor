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
            )
        ]
    
    async def _call_tool(self, name: str, arguments: dict) -> list[TextContent]:
        if name != "launch_claude_code":
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
        
        task = arguments["task"]
        project_path = arguments["project_path"]
        additional_paths = arguments.get("additional_paths", [])
        cli = arguments.get("cli", "claude")
        model = arguments.get("model")
        
        if not Path(project_path).exists():
            return [TextContent(type="text", text=f"Path does not exist: {project_path}")]
        
        full_prompt = f"{task}\n\n{SYSTEM_PROMPT}"
        
        prompt_file = Path(project_path) / "_claude_prompt.txt"
        prompt_file.write_text(full_prompt, encoding='utf-8')
        
        viewer_script = Path(__file__).parent / "gui_viewer.py"
        python_exe = sys.executable
        
        cmd = [python_exe, str(viewer_script), project_path, str(prompt_file)]
        for p in additional_paths:
            if Path(p).exists():
                cmd.extend(["--add-dir", p])
        cmd.extend(["--cli", cli])
        if model:
            cmd.extend(["--model", model])
        
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
            "cli": cli_names.get(cli, cli),
            "model": model or "default",
            "project_path": project_path,
            "additional_paths": additional_paths,
            "message": "GUI window opened with live output. Let me know when it finishes!"
        }
        return [TextContent(type="text", text=json.dumps(response, indent=2))]
    
    async def run(self):
        async with stdio_server() as (read_stream, write_stream):
            await self._server.run(read_stream, write_stream, self._server.create_initialization_options())


def main():
    server = ClaudeCodeMCPServer()
    asyncio.run(server.run())


if __name__ == "__main__":
    main()
