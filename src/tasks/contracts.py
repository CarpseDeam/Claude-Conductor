"""Data contracts for task tracking."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class TaskStatus(Enum):
    """Status of a tracked task."""
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TaskRecord:
    """Record of a dispatched coding task."""
    task_id: str
    project_path: str
    cli: str
    status: TaskStatus
    started_at: datetime
    completed_at: datetime | None = None
    files_modified: list[str] = field(default_factory=list)
    summary: str | None = None
    error: str | None = None

    def to_dict(self) -> dict:
        """Serialize to dictionary for JSON storage."""
        return {
            "task_id": self.task_id,
            "project_path": self.project_path,
            "cli": self.cli,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "files_modified": self.files_modified,
            "summary": self.summary,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TaskRecord":
        """Deserialize from dictionary."""
        return cls(
            task_id=data["task_id"],
            project_path=data["project_path"],
            cli=data["cli"],
            status=TaskStatus(data["status"]),
            started_at=datetime.fromisoformat(data["started_at"]),
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            files_modified=data.get("files_modified", []),
            summary=data.get("summary"),
            error=data.get("error"),
        )
