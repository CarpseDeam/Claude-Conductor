"""PySide6 main window for Claude/Gemini CLI output with session support."""
import json
import subprocess
import threading
import time
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QTextBrowser, QStatusBar
from PySide6.QtCore import QObject, Signal, QTimer
from PySide6.QtGui import QTextCursor, QTextOption

from gui.theme import STYLESHEET, COLORS
from gui.formatters import (
    format_claude_line, format_gemini_line,
    format_summary_card, format_turn_separator,
)
from gui.session import SessionListener

if TYPE_CHECKING:
    from git.contracts import WorkflowResult

logger = logging.getLogger(__name__)

GODOT_EXE = r"C:\Users\carps\OneDrive\Desktop\Godot.exe"

CLI_CONFIGS = {
    "claude": {
        "cmd": "claude -p --permission-mode bypassPermissions --output-format stream-json --include-partial-messages --verbose --max-turns 50",
        "add_dir_flag": "--add-dir",
        "model_flag": "--model",
        "title": "Claude Code",
        "uses_stdin": True,
        "default_model": "sonnet",
        "models": ["opus", "sonnet"],
    },
    "gemini": {
        "cmd": "gemini --output-format stream-json --approval-mode yolo",
        "add_dir_flag": None,
        "model_flag": "-m",
        "title": "Gemini CLI",
        "uses_stdin": True,
        "default_model": "gemini-3-pro-preview",
        "models": ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-3-pro-preview"],
    },
    "codex": {
        "cmd": "codex exec --json --full-auto",
        "add_dir_flag": None,
        "model_flag": "--model",
        "title": "OpenAI Codex",
        "uses_stdin": False,
        "default_model": "gpt-5-codex",
        "models": ["gpt-5-codex", "gpt-5.2-codex"],
    },
}


class _Signals(QObject):
    append_html = Signal(str)
    set_status = Signal(str, str)
    show_summary = Signal()
    new_prompt = Signal(str)


class ClaudeOutputWindow(QMainWindow):

    def __init__(self, project_path: str, prompt: str, additional_dirs: list = None,
                 prompt_file: str = None, cli: str = "claude", model: str = None,
                 git_branch: str = None, godot_project: str = None, task_id: str = None):
        self._app = QApplication.instance() or QApplication([])
        super().__init__()

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
        self._task_reported = False
        self._process = None
        self._session_id: str | None = None
        self._turn_number = 1
        self._stats = self._fresh_stats()
        self._state: dict = {"last_tool_type": None, "last_bash_command": None}
        self._signals = _Signals()
        self._elapsed = 0
        self._session_listener: SessionListener | None = None

        self._build_ui()
        self._connect_signals()
        self._start_session_listener()

    def _fresh_stats(self) -> dict:
        return {
            "files_read": [], "files_written": [], "tools_used": 0,
            "errors": 0, "start_time": time.time(), "cli_output": [],
        }

    def _build_ui(self) -> None:
        model_display = self._model.split("-")[-1] if self._model else ""
        self.setWindowTitle(f"{self._config['title']} ({model_display}) — {Path(self._project_path).name}")
        self.resize(960, 640)
        self.setStyleSheet(STYLESHEET)

        central = QWidget(objectName="central")
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header_text = f"Project: {self._project_path}"
        if self._additional_dirs:
            extras = ", ".join(Path(d).name for d in self._additional_dirs)
            header_text += f"  (+{extras})"
        header = QLabel(header_text, objectName="header")
        layout.addWidget(header)

        self._output = QTextBrowser()
        self._output.setReadOnly(True)
        self._output.setOpenExternalLinks(False)
        self._output.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        layout.addWidget(self._output)

        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)
        self._statusbar.showMessage("Starting...")

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick_elapsed)
        self._timer.start(1000)

    def _connect_signals(self) -> None:
        self._signals.append_html.connect(self._append_html)
        self._signals.set_status.connect(self._set_status)
        self._signals.show_summary.connect(self._show_summary)
        self._signals.new_prompt.connect(self._handle_followup)

    def _start_session_listener(self) -> None:
        """Start TCP listener and register port with task tracker."""
        self._session_listener = SessionListener(
            on_prompt=lambda prompt: self._signals.new_prompt.emit(prompt)
        )
        port = self._session_listener.start()
        self._update_task_port(port)

    def _update_task_port(self, port: int) -> None:
        """Write socket port to task record so server can find us."""
        if not self._task_id:
            return
        try:
            from tasks.tracker import TaskTracker
            record = TaskTracker().get_task(self._task_id)
            if record:
                record.socket_port = port
                TaskTracker()._save(record)
        except Exception as e:
            logger.warning(f"Failed to update task port: {e}")

    def _update_task_session_id(self) -> None:
        """Write captured session_id to task record."""
        if not self._task_id or not self._session_id:
            return
        try:
            from tasks.tracker import TaskTracker
            record = TaskTracker().get_task(self._task_id)
            if record:
                record.session_id = self._session_id
                TaskTracker()._save(record)
        except Exception as e:
            logger.warning(f"Failed to update session_id: {e}")

    def _tick_elapsed(self) -> None:
        self._elapsed += 1
        msg = self._statusbar.currentMessage()
        if msg.startswith("Running"):
            self._statusbar.showMessage(f"Running... {self._elapsed}s")

    def _append_html(self, html: str) -> None:
        cursor = self._output.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertHtml(html)
        self._output.setTextCursor(cursor)
        self._output.ensureCursorVisible()

    def _set_status(self, text: str, color: str = COLORS["accent_green"]) -> None:
        self._statusbar.showMessage(text)
        self._statusbar.setStyleSheet(f"color: {color};")

    # --- Turn execution ---

    def _run_worker(self) -> None:
        """Run the initial prompt as turn 1."""
        success = self._run_single_phase(self._prompt)
        self._signals.show_summary.emit()
        if success:
            self._signals.set_status.emit("Session ready — waiting for follow-up", COLORS["accent_green"])
            self._report_task_completion()
            threading.Thread(target=self._auto_git_commit, daemon=True).start()
        else:
            self._signals.set_status.emit("Failed", COLORS["accent_yellow"])
            self._report_task_failure("CLI execution failed")

    def _handle_followup(self, prompt: str) -> None:
        """Handle a follow-up prompt from the session listener (runs on main thread via signal)."""
        self._turn_number += 1
        self._state = {"last_tool_type": None, "last_bash_command": None}
        self._stats["start_time"] = time.time()
        self._elapsed = 0

        self._append_html(format_turn_separator(self._turn_number))
        threading.Thread(
            target=self._run_followup_worker, args=(prompt,), daemon=True
        ).start()

    def _run_followup_worker(self, prompt: str) -> None:
        """Run a follow-up prompt using --resume."""
        self._signals.set_status.emit("Running... 0s", COLORS["accent_green"])
        success = self._run_single_phase(prompt, resume=True)
        self._signals.show_summary.emit()
        if success:
            self._signals.set_status.emit("Session ready — waiting for follow-up", COLORS["accent_green"])
            threading.Thread(target=self._auto_git_commit, daemon=True).start()
        else:
            self._signals.set_status.emit("Turn failed", COLORS["accent_yellow"])

    def _run_single_phase(self, prompt: str, resume: bool = False) -> bool:
        """Run a single CLI invocation. Captures session_id from first turn."""
        cmd = self._build_cmd(prompt, resume)

        model_display = self._model or "default"
        if resume:
            self._signals.append_html.emit(
                f"<span style='color:{COLORS['text_muted']};'>Resuming session ({model_display})...</span><br><br>"
            )
        else:
            self._signals.append_html.emit(
                f"<span style='color:{COLORS['text_muted']};'>Starting {self._config['title']} ({model_display})...</span><br><br>"
            )
        self._signals.set_status.emit("Running... 0s", COLORS["accent_green"])

        formatter = format_gemini_line if self._cli == "gemini" else format_claude_line

        try:
            popen_kwargs = dict(
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, cwd=self._project_path,
                shell=True, encoding="utf-8", errors="replace",
            )
            if self._config["uses_stdin"]:
                self._process = subprocess.Popen(cmd, stdin=subprocess.PIPE, **popen_kwargs)
                self._process.stdin.write(prompt)
                self._process.stdin.close()
            else:
                self._process = subprocess.Popen(cmd, **popen_kwargs)

            while True:
                line = self._process.stdout.readline()
                if not line and self._process.poll() is not None:
                    break
                if not line:
                    continue

                self._try_capture_session_id(line)

                for seg in formatter(line, self._stats, self._state):
                    self._signals.append_html.emit(seg.html)
                    if seg.html.strip():
                        self._stats["cli_output"].append(seg.html)

            self._process.wait()
            return self._process.returncode == 0

        except Exception as e:
            self._signals.append_html.emit(
                f"<br><span style='color:{COLORS['accent_red']};'>ERROR: {e}</span><br>"
            )
            return False

    def _build_cmd(self, prompt: str, resume: bool) -> str:
        """Build the CLI command string."""
        cmd = self._config["cmd"]

        if resume and self._session_id and self._cli == "claude":
            cmd = f"{cmd} --resume {self._session_id}"

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
            escaped = prompt.replace('"', '\\"')
            cmd = f'{cmd} "{escaped}"'

        return cmd

    def _try_capture_session_id(self, line: str) -> None:
        """Extract session_id from Claude's JSON stream on first turn."""
        if self._session_id:
            return
        try:
            data = json.loads(line)
            sid = data.get("session_id")
            if sid:
                self._session_id = sid
                self._update_task_session_id()
                logger.info(f"Captured session_id: {sid}")
        except (json.JSONDecodeError, KeyError):
            pass

    # --- Summary & reporting ---

    def _show_summary(self) -> None:
        if self._godot_project:
            self._append_html(self._godot_html())
        self._append_html(format_summary_card(self._stats))

    def _godot_html(self) -> str:
        if not Path(GODOT_EXE).exists():
            return ""
        try:
            result = subprocess.run(
                [GODOT_EXE, "--headless", "--quit", "--path", self._godot_project],
                capture_output=True, text=True, timeout=30,
            )
            errors = sum(1 for ln in result.stderr.split("\n") if "ERROR" in ln or "error" in ln.lower())
            if errors == 0:
                return f"<span style='color:{COLORS['accent_green']};'>Godot: ✓ Compiles clean</span><br>"
            return f"<span style='color:{COLORS['accent_red']};'>Godot: ✗ {errors} errors</span><br>"
        except Exception as e:
            logger.warning(f"Godot validation failed: {e}")
            return ""

    def _report_task_completion(self) -> None:
        if not self._task_id:
            return
        self._task_reported = True
        try:
            from tasks.tracker import TaskTracker
            duration = int(time.time() - self._stats["start_time"])
            summary = (f"Duration: {duration}s, Files read: {len(self._stats['files_read'])}, "
                       f"Files modified: {len(self._stats['files_written'])}, "
                       f"Tool calls: {self._stats['tools_used']}, Errors: {self._stats['errors']}")
            cli_output = "".join(self._stats.get("cli_output", []))[-500:]
            TaskTracker().complete_task(self._task_id, self._stats["files_written"], summary, cli_output)
        except Exception as e:
            self._signals.set_status.emit(f"⚠ Task report failed: {e}", COLORS["accent_yellow"])

    def _report_task_failure(self, error: str) -> None:
        if not self._task_id:
            return
        self._task_reported = True
        try:
            from tasks.tracker import TaskTracker
            TaskTracker().fail_task(self._task_id, error)
        except Exception as e:
            self._signals.set_status.emit(f"⚠ Task report failed: {e}", COLORS["accent_yellow"])

    # --- Git & pipelines ---

    def _auto_git_commit(self) -> None:
        if not (Path(self._project_path) / ".git").exists():
            return
        try:
            from git.workflow import GitWorkflow
            result = GitWorkflow(Path(self._project_path)).run()
            self._signals.set_status.emit(*self._git_status_msg(result))
            if result.committed and result.diff_content:
                self._run_post_commit_pipelines(result.diff_content)
        except Exception as e:
            self._signals.set_status.emit(f"⚠ Git: {e}", COLORS["accent_yellow"])

    def _git_status_msg(self, result: "WorkflowResult") -> tuple[str, str]:
        if result.committed and result.commit_message:
            preview = result.commit_message[:50]
            label = "✓ Committed & pushed" if result.pushed else "✓ Committed locally"
            return f"{label}: {preview}", COLORS["accent_green"]
        if result.errors and "No changes to commit" not in result.errors[0]:
            return f"⚠ Git: {result.errors[0][:60]}", COLORS["accent_yellow"]
        return "Session ready — waiting for follow-up", COLORS["accent_green"]

    def _run_post_commit_pipelines(self, diff_content: str) -> None:
        self._signals.set_status.emit("Updating docs...", COLORS["accent_yellow"])
        try:
            from pipelines.runner import PipelineRunner
            PipelineRunner(Path(self._project_path)).run_post_commit(diff_content)
            self._signals.set_status.emit("✓ Docs pipeline dispatched", COLORS["accent_green"])
        except Exception as e:
            self._signals.set_status.emit(f"⚠ Pipeline: {e}", COLORS["accent_yellow"])

    # --- Lifecycle ---

    def closeEvent(self, event) -> None:
        if self._session_listener:
            self._session_listener.stop()
        if self._process and self._process.poll() is None:
            self._process.terminate()
        if self._task_id and not self._task_reported:
            self._report_task_failure("Window closed before task completed")
        if self._prompt_file:
            Path(self._prompt_file).unlink(missing_ok=True)
        event.accept()

    def run(self) -> None:
        self.show()
        threading.Thread(target=self._run_worker, daemon=True).start()
        self._app.exec()
