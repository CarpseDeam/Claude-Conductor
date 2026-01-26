from dataclasses import dataclass, field


@dataclass
class GitDiff:
    content: str
    files_changed: list[str]
    has_changes: bool


@dataclass
class CommitResult:
    success: bool
    hash: str | None
    message: str
    error: str | None = None


@dataclass
class WorkflowResult:
    committed: bool
    pushed: bool
    merged: bool
    branch_cleaned: bool
    commit_message: str | None
    diff_content: str | None = None
    errors: list[str] = field(default_factory=list)
