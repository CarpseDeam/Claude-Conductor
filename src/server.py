import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import asyncio
import json
import subprocess
from datetime import datetime
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent


GODOT_EXE = r"C:\Users\carps\OneDrive\Desktop\Godot.exe"

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
    
    def _create_git_branch(self, project_path: str) -> str | None:
        git_dir = Path(project_path) / ".git"
        if not git_dir.exists():
            return None
        
        branch_name = f"claude/{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        try:
            subprocess.run(
                ["git", "stash", "-u"],
                cwd=project_path,
                capture_output=True,
                timeout=10
            )
            
            result = subprocess.run(
                ["git", "checkout", "-b", branch_name],
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                return branch_name
            return None
        except Exception:
            return None
    
    def _get_godot_errors(self, godot_project: str) -> list[str] | None:
        if not Path(GODOT_EXE).exists():
            return None
        
        if not Path(godot_project).exists():
            return None
        
        try:
            result = subprocess.run(
                [GODOT_EXE, "--headless", "--quit", "--path", godot_project],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            errors = []
            for line in result.stderr.split('\n'):
                if 'ERROR' in line or 'SCRIPT ERROR' in line:
                    errors.append(line.strip())
            
            return errors if errors else None
        except Exception:
            return None
    
    async def _call_tool(self, name: str, arguments: dict) -> list[TextContent]:
        if name != "launch_claude_code":
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
        
        task = arguments["task"]
        project_path = arguments["project_path"]
        additional_paths = arguments.get("additional_paths", [])
        cli = arguments.get("cli", "claude")
        model = arguments.get("model")
        git_branch_enabled = arguments.get("git_branch", True)
        godot_project = arguments.get("godot_project")
        
        if not Path(project_path).exists():
            return [TextContent(type="text", text=f"Path does not exist: {project_path}")]
        
        branch_name = None
        if git_branch_enabled:
            branch_name = self._create_git_branch(project_path)
        
        godot_errors = None
        if godot_project:
            godot_errors = self._get_godot_errors(godot_project)
        
        full_prompt = task
        
        if godot_errors:
            errors_text = "\n".join(godot_errors)
            full_prompt = (
                f"CURRENT GODOT COMPILE ERRORS (fix these if relevant to your task):\n"
                f"```\n{errors_text}\n```\n\n"
                f"{task}"
            )
        
        full_prompt = f"{full_prompt}\n\n{SYSTEM_PROMPT}"
        
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
        
        if branch_name:
            cmd.extend(["--git-branch", branch_name])
        
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
            "cli": cli_names.get(cli, cli),
            "model": model or "default",
            "project_path": project_path,
            "additional_paths": additional_paths,
            "git_branch": branch_name,
            "godot_errors_found": len(godot_errors) if godot_errors else 0,
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
