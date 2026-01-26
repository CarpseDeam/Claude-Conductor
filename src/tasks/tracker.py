"""Task tracking for dispatched coding tasks."""

import json
import uuid
from datetime import datetime
from pathlib import Path

from .contracts import TaskRecord, TaskStatus


class TaskTracker:
    """Tracks dispatched tasks and their results."""

    STORAGE_DIR = Path.home() / ".conductor" / "tasks"

    def __init__(self) -> None:
        self.STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    def create_task(self, project_path: str, cli: str) -> str:
        """Create new task record, return task_id."""
        task_id = uuid.uuid4().hex[:8]
        record = TaskRecord(
            task_id=task_id,
            project_path=project_path,
            cli=cli,
            status=TaskStatus.RUNNING,
            started_at=datetime.now(),
        )
        self._save(record)
        return task_id

    def complete_task(self, task_id: str, files_modified: list[str], summary: str, cli_output: str | None = None) -> None:
        """Mark task as completed with results."""
        record = self.get_task(task_id)
        if not record:
            return
        record.status = TaskStatus.COMPLETED
        record.completed_at = datetime.now()
        record.files_modified = files_modified
        record.summary = summary
        record.cli_output = cli_output
        self._save(record)

    def fail_task(self, task_id: str, error: str) -> None:
        """Mark task as failed."""
        record = self.get_task(task_id)
        if not record:
            return
        record.status = TaskStatus.FAILED
        record.completed_at = datetime.now()
        record.error = error
        self._save(record)

    def get_task(self, task_id: str) -> TaskRecord | None:
        """Retrieve task record."""
        path = self.STORAGE_DIR / f"{task_id}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return TaskRecord.from_dict(data)
        except (json.JSONDecodeError, KeyError, ValueError):
            return None

    def get_recent_tasks(self, limit: int = 10) -> list[TaskRecord]:
        """Get most recent tasks sorted by modification time."""
        tasks: list[TaskRecord] = []
        task_files = sorted(
            self.STORAGE_DIR.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for path in task_files[:limit]:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                record = TaskRecord.from_dict(data)
                tasks.append(record)
            except (json.JSONDecodeError, KeyError, ValueError):
                continue
        return tasks

    def _save(self, record: TaskRecord) -> None:
        """Persist task record to disk."""
        path = self.STORAGE_DIR / f"{record.task_id}.json"
        path.write_text(json.dumps(record.to_dict(), indent=2), encoding="utf-8")
