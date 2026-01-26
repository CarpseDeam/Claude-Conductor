"""Pipeline execution engine."""

import subprocess
import logging
import tempfile
import os
from pathlib import Path

from .config import PipelineConfig, PipelineStep

logger = logging.getLogger(__name__)

CLI_COMMANDS = {
    "gemini": "gemini",
    "claude": "claude",
}


class PipelineRunner:
    """Executes post-commit pipelines."""

    def __init__(self, project_path: Path):
        self.project_path = project_path
        self.config = PipelineConfig.load(project_path)

    def run_post_commit(self, diff: str) -> None:
        """Run all enabled post-commit pipelines. Non-blocking."""
        from .auto_docs import ensure_doc_structure
        ensure_doc_structure(self.project_path)

        for step in self.config.post_commit:
            if not step.enabled:
                continue

            if not self._check_condition(step, diff):
                continue

            self._dispatch_step(step, diff)

    def _check_condition(self, step: PipelineStep, diff: str) -> bool:
        """Check if pipeline should run based on conditions."""
        if not diff.strip():
            return False
        return True

    def _dispatch_step(self, step: PipelineStep, diff: str) -> None:
        """Dispatch pipeline step to agent. Non-blocking."""
        task = step.task_template.format(diff=diff)
        cli_cmd = CLI_COMMANDS.get(step.agent, "gemini")

        logger.info(f"Dispatching pipeline '{step.name}' to {step.agent}")

        try:
            creationflags = 0
            try:
                creationflags = subprocess.CREATE_NO_WINDOW
            except AttributeError:
                pass

            with tempfile.NamedTemporaryFile(
                mode='w', suffix='.txt', delete=False, encoding='utf-8'
            ) as f:
                f.write(task)
                prompt_file = f.name

            if step.agent == "gemini":
                cmd = f'type "{prompt_file}" | gemini --approval-mode yolo'
                if step.model:
                    cmd += f' -m {step.model}'

                subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    cwd=str(self.project_path),
                    shell=True,
                    creationflags=creationflags
                )
            else:
                cmd = f"{cli_cmd} -p"
                if step.model:
                    cmd += f" -m {step.model}"

                process = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    cwd=str(self.project_path),
                    shell=True,
                    creationflags=creationflags
                )
                process.stdin.write(task)
                process.stdin.close()

                try:
                    os.unlink(prompt_file)
                except OSError:
                    pass

        except Exception as e:
            logger.error(f"Pipeline dispatch failed: {e}")
