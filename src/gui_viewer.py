import subprocess
import threading
import tkinter as tk
from tkinter import scrolledtext
from pathlib import Path
import sys
import json
import time
import logging
from typing import TYPE_CHECKING

from output.masker import mask_output, CommandType

if TYPE_CHECKING:
    from git.contracts import WorkflowResult

logger = logging.getLogger(__name__)

GODOT_EXE = r"C:\Users\carps\OneDrive\Desktop\Godot.exe"


CLI_CONFIGS = {
    "claude": {
        "cmd": "claude -p --model opus --output-format stream-json --include-partial-messages --verbose --max-turns 25 --dangerously-skip-permissions",
        "add_dir_flag": "--add-dir",
        "model_flag": "--model",
        "title": "Claude Code",
        "uses_stdin": True,
        "default_model": "opus",
        "models": ["opus", "sonnet"]
    },
    "gemini": {
        "cmd": 'gemini --output-format stream-json --approval-mode yolo --allowed-tools "Bash,Edit,WriteFile,ReadFile,Glob,Grep,Shell,Replace,SearchText,FindFiles,ListDirectory,WebFetch,GoogleSearch"',
        "add_dir_flag": None,
        "model_flag": "-m",
        "title": "Gemini CLI",
        "uses_stdin": True,
        "default_model": "gemini-3-pro-preview",
        "models": ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-3-pro-preview"]
    },
    "codex": {
        "cmd": "codex exec --json --full-auto",
        "add_dir_flag": None,
        "model_flag": "--model",
        "title": "OpenAI Codex",
        "uses_stdin": False,
        "default_model": "gpt-5-codex",
        "models": ["gpt-5-codex", "gpt-5.2-codex"]
    }
}


class ClaudeOutputWindow:

    def __init__(self, project_path: str, prompt: str, additional_dirs: list = None,
                 prompt_file: str = None, cli: str = "claude", model: str = None,
                 git_branch: str = None, godot_project: str = None, task_id: str = None):
        self._project_path = project_path
        self._prompt = prompt
        self._additional_dirs = additional_dirs or []
        self._prompt_file = prompt_file
        self._cli = cli
        self._config = CLI_CONFIGS.get(cli, CLI_CONFIGS["claude"])
        self._model = model or self._config.get("default_model")
        self._git_branch = git_branch
        self._godot_project = godot_project
        self._task_id = task_id
        self._process = None
        self._stats = self._init_stats()
        self._last_tool_type = None
        self._last_bash_command: str | None = None

        self._root = tk.Tk()
        model_display = self._model.split("-")[-1] if self._model else ""
        self._root.title(f"{self._config['title']} ({model_display}) - {Path(project_path).name}")
        self._root.geometry("900x600")
        self._root.configure(bg="#1e1e1e")
        
        self._build_ui()
    
    def _build_ui(self):
        header_text = f"Project: {self._project_path}"
        if self._additional_dirs:
            extras = ", ".join(Path(d).name for d in self._additional_dirs)
            header_text += f"  (+{extras})"
        
        header = tk.Label(
            self._root,
            text=header_text,
            bg="#1e1e1e",
            fg="#888888",
            anchor="w",
            padx=10,
            pady=5
        )
        header.pack(fill="x")
        
        self._output = scrolledtext.ScrolledText(
            self._root,
            wrap=tk.WORD,
            bg="#0d0d0d",
            fg="#00ff00",
            font=("Consolas", 10),
            insertbackground="#00ff00",
            padx=10,
            pady=10
        )
        self._output.pack(fill="both", expand=True, padx=5, pady=5)

        self._configure_tags()

        self._status = tk.Label(
            self._root,
            text="Starting...",
            bg="#1e1e1e",
            fg="#00ff00",
            anchor="w",
            padx=10,
            pady=5
        )
        self._status.pack(fill="x")
        
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _init_stats(self) -> dict:
        return {
            "files_read": [],
            "files_written": [],
            "tools_used": 0,
            "errors": 0,
            "start_time": time.time()
        }

    def _configure_tags(self):
        self._output.tag_configure("tool", foreground="#FFD700")
        self._output.tag_configure("success", foreground="#00FF00")
        self._output.tag_configure("error", foreground="#FF4444")
        self._output.tag_configure("info", foreground="#00FFFF")
        self._output.tag_configure("text", foreground="#FFFFFF")
        self._output.tag_configure("muted", foreground="#888888")

    def _append(self, text: str, tag: str = "text"):
        self._output.insert(tk.END, text, tag)
        self._output.see(tk.END)
    
    def _set_status(self, text: str, color: str = "#00ff00"):
        self._status.config(text=text, fg=color)
    
    def _run_claude(self):
        cmd = self._config["cmd"]
        
        if self._model and self._config.get("model_flag"):
            cmd = f'{cmd} {self._config["model_flag"]} {self._model}'
        
        if self._additional_dirs:
            if self._config["add_dir_flag"]:
                add_dirs = " ".join(f'{self._config["add_dir_flag"]} "{d}"' for d in self._additional_dirs)
                cmd = f"{cmd} {add_dirs}"
            elif self._cli == "gemini":
                dirs_csv = ",".join(self._additional_dirs)
                cmd = f'{cmd} --include-directories "{dirs_csv}"'
        
        if not self._config["uses_stdin"]:
            escaped_prompt = self._prompt.replace('"', '\\"')
            cmd = f'{cmd} "{escaped_prompt}"'
        
        model_display = self._model or "default"
        self._root.after(0, lambda: self._append(f"Starting {self._config['title']} ({model_display})...\n\n"))
        self._root.after(0, lambda: self._set_status("Running..."))
        
        try:
            if self._config["uses_stdin"]:
                self._process = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    cwd=self._project_path,
                    shell=True,
                    encoding='utf-8',
                    errors='replace'
                )
                self._process.stdin.write(self._prompt)
                self._process.stdin.close()
            else:
                self._process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    cwd=self._project_path,
                    shell=True,
                    encoding='utf-8',
                    errors='replace'
                )
            
            for line in iter(self._process.stdout.readline, ""):
                segments = self._format_line(line)
                for text, tag in segments:
                    self._root.after(0, lambda t=text, g=tag: self._append(t, g))

            self._process.wait()
            self._root.after(0, self._show_summary)

            if self._process.returncode == 0:
                self._root.after(0, lambda: self._set_status("Completed successfully!", "#00ff00"))
                self._report_task_completion()
                git_thread = threading.Thread(target=self._auto_git_commit, daemon=True)
                git_thread.start()
            else:
                self._root.after(0, lambda: self._set_status(f"Exited with code {self._process.returncode}", "#ff6600"))
                self._report_task_failure(f"Process exited with code {self._process.returncode}")
        
        except Exception as e:
            self._root.after(0, lambda: self._append(f"\nERROR: {e}\n", "error"))
            self._root.after(0, lambda: self._set_status(f"Error: {e}", "#ff0000"))
            self._report_task_failure(str(e))
    
    def _format_line(self, line: str) -> list:
        if self._cli == "gemini":
            return self._format_line_gemini(line)
        return self._format_line_claude(line)

    def _format_line_claude(self, line: str) -> list:
        try:
            data = json.loads(line)
            msg_type = data.get("type", "")

            if msg_type == "system":
                session = data.get("session_id", "")[:8]
                return [(f"[Session: {session}...]\n", "muted")]

            elif msg_type == "stream_event":
                return self._handle_stream_event(data)

            elif msg_type == "assistant":
                return self._handle_assistant_message(data)

            elif msg_type == "user":
                return self._handle_tool_result(data)

            elif msg_type == "result":
                return [("\n", "text")]

            return []

        except json.JSONDecodeError:
            return [(line, "text")] if line.strip() else []

    def _format_line_gemini(self, line: str) -> list:
        try:
            data = json.loads(line)
            msg_type = data.get("type", "")

            if msg_type == "init":
                session = data.get("session_id", "")[:8]
                model = data.get("model", "")
                return [(f"[Session: {session}... | Model: {model}]\n", "muted")]

            elif msg_type == "tool_use":
                return self._handle_gemini_tool_use(data)

            elif msg_type == "tool_result":
                return self._handle_gemini_tool_result(data)

            elif msg_type == "message":
                role = data.get("role", "")
                if role == "assistant":
                    content = data.get("content", "")
                    return [(content, "text")] if content else []

            return []

        except json.JSONDecodeError:
            return [(line, "text")] if line.strip() else []

    def _handle_gemini_tool_use(self, data: dict) -> list:
        tool = data.get("tool_name", "?")
        inp = data.get("input", {})
        self._stats["tools_used"] += 1
        if tool in ["Bash", "run_shell_command", "Shell"]:
            self._last_bash_command = inp.get("command", "")
        return self._format_tool_call(tool, inp)

    def _handle_gemini_tool_result(self, data: dict) -> list:
        is_error = data.get("is_error", False)
        output = data.get("output", "")
        result_content = output if isinstance(output, str) else str(output)

        cmd_type = self._detect_command_type(self._last_bash_command or "") if self._last_bash_command else None
        if cmd_type:
            masked = mask_output(result_content, cmd_type)
            self._last_bash_command = None
            if is_error or masked.errors:
                self._stats["errors"] += 1
                return [("  [FAILED] ", "error"), (f"{masked.summary}\n", "error")]
            return [("  [OK] ", "success"), (f"{masked.summary}\n", "muted")]

        max_len = 400 if is_error else 150
        result_content = result_content[:max_len].replace("\n", " ").strip()

        if is_error:
            self._stats["errors"] += 1
            return [("  [FAILED] ", "error"), (f"{result_content}\n", "error")]

        segments = [("  [OK] ", "success")]
        if result_content:
            preview = result_content[:100] + "..." if len(result_content) > 100 else result_content
            segments.append((f"{preview}\n", "muted"))
        else:
            segments.append(("\n", "text"))
        return segments

    def _handle_assistant_message(self, data: dict) -> list:
        content = data.get("message", {}).get("content", [])
        segments = []
        for block in content:
            if block.get("type") == "tool_use":
                tool = block.get("name", "?")
                inp = block.get("input", {})
                self._stats["tools_used"] += 1
                segments.extend(self._format_tool_call(tool, inp))
        return segments

    def _format_tool_call(self, tool: str, inp: dict) -> list:
        tool_type = self._get_tool_type(tool)
        segments = []

        if tool_type != self._last_tool_type and self._last_tool_type is not None:
            segments.append(("\n", "text"))
        self._last_tool_type = tool_type

        if tool in ["Read", "read_file"]:
            path = inp.get("file_path") or inp.get("path", "")
            filename = Path(path).name if path else "?"
            if path and path not in self._stats["files_read"]:
                self._stats["files_read"].append(path)
            segments.append(("[READ] ", "info"))
            segments.append((f"{filename}\n", "text"))

        elif tool in ["Write", "Edit", "MultiEdit", "write_file"]:
            path = inp.get("file_path") or inp.get("path", "")
            filename = Path(path).name if path else "?"
            if path and path not in self._stats["files_written"]:
                self._stats["files_written"].append(path)
            segments.append(("[EDIT] ", "tool"))
            segments.append((f"{filename}\n", "text"))

        elif tool in ["Bash", "run_shell_command", "Shell"]:
            cmd = inp.get("command", "")
            self._last_bash_command = cmd
            segments.append(("[BASH] ", "tool"))
            segments.append((f"{cmd[:80]}\n", "muted"))

        elif tool in ["Glob", "Grep", "FindFiles", "SearchText"]:
            pattern = inp.get("pattern", "")[:60]
            segments.append(("[SEARCH] ", "info"))
            segments.append((f"{pattern}\n", "muted"))

        elif tool in ["LS", "list_directory", "ReadFolder"]:
            path = inp.get("path", ".")[:40]
            segments.append(("[LS] ", "info"))
            segments.append((f"{path}\n", "muted"))

        elif tool in ["TodoWrite", "WriteTodos", "write_todos"]:
            segments.extend(self._format_todos(inp.get("todos", [])))

        else:
            detail = self._get_tool_detail(tool, inp)
            segments.append((f"[{tool.upper()}] ", "tool"))
            segments.append((f"{detail}\n", "muted"))

        return segments

    def _get_tool_type(self, tool: str) -> str:
        if tool in ["Read", "read_file"]:
            return "read"
        elif tool in ["Write", "Edit", "MultiEdit", "write_file"]:
            return "write"
        elif tool in ["Bash", "run_shell_command", "Shell"]:
            return "bash"
        elif tool in ["Glob", "Grep", "FindFiles", "SearchText", "LS", "list_directory", "ReadFolder"]:
            return "search"
        return "other"

    def _detect_command_type(self, cmd: str) -> CommandType | None:
        """Detect if a bash command is a validation command."""
        cmd_lower = cmd.lower()
        if "pytest" in cmd_lower:
            return CommandType.PYTEST
        elif "mypy" in cmd_lower:
            return CommandType.MYPY
        elif any(x in cmd_lower for x in ["ruff", "flake8", "lint"]):
            return CommandType.LINT
        return None

    def _handle_tool_result(self, data: dict) -> list:
        content = data.get("message", {}).get("content", [])
        segments = []
        for block in content:
            if block.get("type") == "tool_result":
                is_error = block.get("is_error", False)
                result_content = block.get("content", "")
                if isinstance(result_content, list):
                    result_content = str(result_content[0].get("text", ""))
                else:
                    result_content = str(result_content)

                cmd_type = self._detect_command_type(self._last_bash_command or "") if self._last_bash_command else None
                if cmd_type:
                    masked = mask_output(result_content, cmd_type)
                    self._last_bash_command = None
                    if is_error or masked.errors:
                        self._stats["errors"] += 1
                        segments.append(("  [FAILED] ", "error"))
                        segments.append((f"{masked.summary}\n", "error"))
                    else:
                        segments.append(("  [OK] ", "success"))
                        segments.append((f"{masked.summary}\n", "muted"))
                    continue

                max_len = 400 if is_error else 150
                result_content = result_content[:max_len].replace("\n", " ").strip()

                if is_error:
                    self._stats["errors"] += 1
                    segments.append(("  [FAILED] ", "error"))
                    segments.append((f"{result_content}\n", "error"))
                else:
                    segments.append(("  [OK] ", "success"))
                    if result_content:
                        preview = result_content[:100] + "..." if len(result_content) > 100 else result_content
                        segments.append((f"{preview}\n", "muted"))
                    else:
                        segments.append(("\n", "text"))
        return segments
    
    def _get_tool_detail(self, tool: str, inp: dict) -> str:
        if tool in ["TodoRead"]:
            return "reading todos"
        return ""
    
    def _format_todos(self, todos: list) -> list:
        if not todos:
            return []
        segments = []
        segments.append(("\n  ┌─ TODO LIST ─────────────────────────\n", "muted"))
        for t in todos:
            status = t.get("status", "pending")
            content = t.get("content", "")[:50]

            if status == "completed":
                icon = "✓"
                tag = "success"
            elif status == "in_progress":
                icon = "►"
                tag = "tool"
            else:
                icon = "○"
                tag = "muted"

            segments.append((f"  │ {icon} ", tag))
            segments.append((f"{content}\n", "text"))
        segments.append(("  └────────────────────────────────────\n", "muted"))
        return segments
    
    def _handle_stream_event(self, data: dict) -> list:
        event = data.get("event", {})
        event_type = event.get("type", "")

        if event_type == "content_block_delta":
            delta = event.get("delta", {})
            if delta.get("type") == "text_delta":
                return [(delta.get("text", ""), "text")]
            elif delta.get("type") == "input_json_delta":
                return []

        elif event_type == "content_block_start":
            block = event.get("content_block", {})
            if block.get("type") == "tool_result":
                is_error = block.get("is_error", False)
                content = block.get("content", "")[:400 if is_error else 200]
                if is_error:
                    self._stats["errors"] += 1
                    return [("\n[ERROR] ", "error"), (f"{content}\n", "error")]
                return [("  [OK] ", "success"), (f"{content[:80]}...\n", "muted")]

        elif event_type == "message_start":
            model = event.get("message", {}).get("model", "")
            if model:
                return [(f"[Model: {model}]\n\n", "muted")]

        return []

    def _run_godot_validation(self) -> int | None:
        if not self._godot_project:
            return None
        if not Path(GODOT_EXE).exists():
            logger.warning(f"Godot executable not found: {GODOT_EXE}")
            return None
        try:
            result = subprocess.run(
                [GODOT_EXE, "--headless", "--quit", "--path", self._godot_project],
                capture_output=True, text=True, timeout=30
            )
            error_count = len([
                line for line in result.stderr.split('\n')
                if 'ERROR' in line or 'error' in line.lower()
            ])
            return error_count
        except Exception as e:
            logger.warning(f"Godot validation failed: {e}")
            return None

    def _append_tagged(self, segments: list):
        for text, tag in segments:
            self._append(text, tag)

    def _show_summary(self):
        duration = int(time.time() - self._stats["start_time"])
        files_read = len(self._stats["files_read"])
        files_written = self._stats["files_written"]
        tools_used = self._stats["tools_used"]
        errors = self._stats["errors"]

        modified_names = ", ".join(Path(f).name for f in files_written[:5])
        if len(files_written) > 5:
            modified_names += f", +{len(files_written) - 5} more"

        self._append("\n", "text")
        self._append("┌─ SUMMARY ────────────────────────────\n", "info")
        self._append(f"│ Duration: {duration}s\n", "text")
        self._append(f"│ Files read: {files_read}\n", "text")

        if files_written:
            self._append(f"│ Files modified: {len(files_written)} ({modified_names})\n", "success")
        else:
            self._append("│ Files modified: 0\n", "text")

        self._append(f"│ Tool calls: {tools_used}\n", "text")

        if errors > 0:
            self._append(f"│ Errors: {errors}\n", "error")
        else:
            self._append("│ Errors: 0\n", "success")

        if self._godot_project:
            error_count = self._run_godot_validation()
            if error_count is not None:
                if error_count == 0:
                    self._append_tagged([("│ Godot: ✓ Compiles clean\n", "success")])
                else:
                    self._append_tagged([("│ Godot: ✗ ", "error"), (f"{error_count} errors\n", "error")])

        self._append("└──────────────────────────────────────\n", "info")

    def _report_task_completion(self) -> None:
        """Report task completion to tracker."""
        if not self._task_id:
            return
        try:
            from tasks.tracker import TaskTracker
            tracker = TaskTracker()
            files_modified = self._stats.get("files_written", [])
            summary = self._build_summary()
            tracker.complete_task(self._task_id, files_modified, summary)
        except Exception as e:
            logger.warning(f"Failed to report task completion: {e}")

    def _report_task_failure(self, error: str) -> None:
        """Report task failure to tracker."""
        if not self._task_id:
            return
        try:
            from tasks.tracker import TaskTracker
            tracker = TaskTracker()
            tracker.fail_task(self._task_id, error)
        except Exception as e:
            logger.warning(f"Failed to report task failure: {e}")

    def _build_summary(self) -> str:
        """Build summary string from stats."""
        duration = int(time.time() - self._stats["start_time"])
        files_read = len(self._stats["files_read"])
        files_written = len(self._stats["files_written"])
        tools_used = self._stats["tools_used"]
        errors = self._stats["errors"]
        return f"Duration: {duration}s, Files read: {files_read}, Files modified: {files_written}, Tool calls: {tools_used}, Errors: {errors}"

    def _auto_git_commit(self) -> None:
        """Run git commit workflow in background. Non-blocking, errors logged not raised."""
        git_dir = Path(self._project_path) / ".git"
        if not git_dir.exists():
            return

        try:
            from git.workflow import GitWorkflow
            workflow = GitWorkflow(Path(self._project_path))
            result = workflow.run()
            self._root.after(0, lambda: self._update_git_status(result))
        except Exception as e:
            self._root.after(0, lambda: self._set_status(f"⚠ Git: {e}", "#FFA500"))

    def _update_git_status(self, result: "WorkflowResult") -> None:
        """Update status bar with git operation result."""
        if result.committed and result.commit_message:
            msg_preview = result.commit_message[:50]
            if result.pushed:
                self._set_status(f"✓ Committed & pushed: {msg_preview}", "#00ff00")
            else:
                self._set_status(f"✓ Committed locally: {msg_preview}", "#00ff00")
            if result.diff_content:
                self._run_post_commit_pipelines(result.diff_content)
        elif result.errors:
            if "No changes to commit" in result.errors:
                pass
            else:
                first_error = result.errors[0][:60]
                self._set_status(f"⚠ Git: {first_error}", "#FFA500")

    def _run_post_commit_pipelines(self, diff_content: str) -> None:
        """Fire post-commit pipelines. Non-blocking."""
        self._root.after(0, lambda: self._set_status("📄 Updating docs...", "#FFD700"))
        try:
            from pipelines.runner import PipelineRunner

            runner = PipelineRunner(Path(self._project_path))
            runner.run_post_commit(diff_content)
            self._root.after(0, lambda: self._set_status("✓ Docs pipeline dispatched", "#00ff00"))
        except Exception as e:
            self._root.after(0, lambda: self._set_status(f"⚠ Pipeline: {e}", "#FFA500"))

    def _on_close(self):
        if self._process and self._process.poll() is None:
            self._process.terminate()
        self._cleanup_prompt_file()
        self._root.destroy()
    
    def _cleanup_prompt_file(self):
        if self._prompt_file:
            try:
                Path(self._prompt_file).unlink(missing_ok=True)
            except:
                pass
    
    def run(self):
        thread = threading.Thread(target=self._run_claude, daemon=True)
        thread.start()
        self._root.mainloop()


def main():
    if len(sys.argv) < 3:
        print("Usage: gui_viewer.py <project_path> <prompt_file> [--add-dir <path>]... [--cli claude|gemini|codex] [--model <model>] [--git-branch <n>] [--godot-project <path>] [--task-id <id>]")
        sys.exit(1)

    project_path = sys.argv[1]
    prompt_file = sys.argv[2]

    additional_dirs = []
    cli = "claude"
    model = None
    git_branch = None
    godot_project = None
    task_id = None

    i = 3
    while i < len(sys.argv):
        if sys.argv[i] == "--add-dir" and i + 1 < len(sys.argv):
            additional_dirs.append(sys.argv[i + 1])
            i += 2
        elif sys.argv[i] == "--cli" and i + 1 < len(sys.argv):
            cli = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--model" and i + 1 < len(sys.argv):
            model = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--git-branch" and i + 1 < len(sys.argv):
            git_branch = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--godot-project" and i + 1 < len(sys.argv):
            godot_project = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--task-id" and i + 1 < len(sys.argv):
            task_id = sys.argv[i + 1]
            i += 2
        else:
            i += 1

    prompt = Path(prompt_file).read_text(encoding="utf-8")

    window = ClaudeOutputWindow(
        project_path, prompt, additional_dirs, prompt_file, cli, model,
        git_branch, godot_project, task_id
    )
    window.run()


if __name__ == "__main__":
    main()
