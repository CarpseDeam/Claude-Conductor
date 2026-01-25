from pathlib import Path

from .contracts import WorkflowResult
from .operations import GitOperations


class GitWorkflow:
    MAIN_BRANCHES = ("main", "master")

    def __init__(self, project_path: Path, current_branch: str | None = None) -> None:
        self.project_path = project_path
        self.ops = GitOperations()
        self.msg_generator = None
        self._current_branch = current_branch

    @property
    def current_branch(self) -> str | None:
        if self._current_branch is None:
            self._current_branch = self.ops.get_current_branch(self.project_path)
        return self._current_branch

    def _get_main_branch(self) -> str:
        return "main"

    def _get_commit_message_generator(self):
        if self.msg_generator is None:
            from .commit_message import CommitMessageGenerator
            self.msg_generator = CommitMessageGenerator()
        return self.msg_generator

    def run(self) -> WorkflowResult:
        errors: list[str] = []
        info: list[str] = []
        committed = False
        pushed = False
        merged = False
        branch_cleaned = False
        commit_message: str | None = None

        diff = self.ops.get_diff(self.project_path)
        if not diff.has_changes:
            return WorkflowResult(
                committed=False,
                pushed=False,
                merged=False,
                branch_cleaned=False,
                commit_message=None,
                errors=["No changes to commit"],
            )

        self.ops.cleanup_artifacts(self.project_path)

        if self.ops.ensure_gitignore(self.project_path):
            diff = self.ops.get_diff(self.project_path)

        if not self.ops.stage_all(self.project_path):
            errors.append("Failed to stage changes")
            return WorkflowResult(
                committed=False,
                pushed=False,
                merged=False,
                branch_cleaned=False,
                commit_message=None,
                errors=errors,
            )

        try:
            generator = self._get_commit_message_generator()
            commit_message = generator.generate(diff)
        except Exception as e:
            errors.append(f"Failed to generate commit message: {e}")
            return WorkflowResult(
                committed=False,
                pushed=False,
                merged=False,
                branch_cleaned=False,
                commit_message=None,
                errors=errors,
            )

        commit_result = self.ops.commit(self.project_path, commit_message)
        if not commit_result.success:
            errors.append(f"Commit failed: {commit_result.error}")
            return WorkflowResult(
                committed=False,
                pushed=False,
                merged=False,
                branch_cleaned=False,
                commit_message=commit_message,
                errors=errors,
            )
        committed = True

        has_remote = self.ops.has_remote(self.project_path)
        if not has_remote:
            info.append("No remote configured, committed locally")
            return WorkflowResult(
                committed=committed,
                pushed=False,
                merged=False,
                branch_cleaned=False,
                commit_message=commit_message,
                errors=info,
            )

        branch = self.current_branch
        if branch and GitOperations.is_claude_branch(branch):
            if self.ops.push(self.project_path, branch):
                pushed = True
            else:
                errors.append(f"Failed to push branch {branch}")

            main_branch = self._get_main_branch()
            if self.ops.checkout(self.project_path, main_branch):
                if self.ops.merge(self.project_path, branch):
                    merged = True
                    if self.ops.push(self.project_path):
                        pass
                    else:
                        errors.append(f"Failed to push {main_branch}")

                    if self.ops.delete_branch(self.project_path, branch):
                        branch_cleaned = True
                    else:
                        errors.append(f"Failed to delete branch {branch}")
                else:
                    errors.append(f"Failed to merge {branch} into {main_branch}")
            else:
                errors.append(f"Failed to checkout {main_branch}")

        elif branch in self.MAIN_BRANCHES:
            if self.ops.push(self.project_path):
                pushed = True
            else:
                errors.append("Failed to push to remote")
        else:
            if self.ops.push(self.project_path, branch):
                pushed = True
            else:
                errors.append(f"Failed to push branch {branch}")

        return WorkflowResult(
            committed=committed,
            pushed=pushed,
            merged=merged,
            branch_cleaned=branch_cleaned,
            commit_message=commit_message,
            errors=errors,
        )
