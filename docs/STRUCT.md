# ClaudeDesktop-ClaudeCode-Bridge

**Language:** python

## Structure

- `.claude/` - Project-level steering (1 file)
- `docs/` - Documentation (4 files)
- `src/` - Source code (3 files)
- `src\dispatch/` - Task dispatch logic (2 files)
- `src\git/` - Project files (5 files)
- `src\mapper/` - Project files (5 files)
- `src\output/` - Output compression (2 files)
- `src\pipelines/` - Project files (4 files)
- `src\specs/` - Project files (6 files)
- `src\tasks/` - Project files (3 files)

## Key Files

- `.claude\steering.md` - Project standards and stack info
- `pyproject.toml` - Project config
- `src\server.py` - Server entry
- `src\pipelines\config.py` - Configuration
- `src\gui_viewer.py` - Source code
- `src\output\masker.py` - Output compression logic
- `src\mapper\mapper.py` - Source code
- `src\mapper\git_info.py` - Source code
- `src\specs\prompts.py` - Source code
- `src\specs\runner.py` - Spec phase execution logic
- `src\specs\validator.py` - Spec validation logic
- `src\git\operations.py` - Source code
- `src\mapper\parser.py` - Source code
- `README.md` - Documentation
- `src\specs\parser.py` - Source code
- `src\git\workflow.py` - Source code
- `docs\API.md` - Documentation
- `docs\ARCHITECTURE.md` - Documentation
- `src\specs\contracts.py` - Data contracts
- `src\pipelines\runner.py` - Source code
- `src\mapper\detector.py` - Source code
- `src\tasks\tracker.py` - Source code
- `_claude_runner.py` - Source code
- `src\tasks\contracts.py` - Data contracts
- `src\git\commit_message.py` - Source code
- `docs\CHANGELOG.md` - Documentation
- `src\git\contracts.py` - Data contracts
- `docs\STRUCT.md` - Documentation
- `src\pipelines\auto_docs.py` - Source code
- `src\git\__init__.py` - Package init
- `src\specs\__init__.py` - Package init
- `src\mapper\__init__.py` - Package init
- `src\__init__.py` - Package init
- `src\pipelines\__init__.py` - Package init
- `src\tasks\__init__.py` - Package init

## Module Details

### `src\output\masker.py`
_Compress verbose CLI output into minimal, actionable summaries._

**Functions**: `mask_output(raw: str, command_type: CommandType) -> MaskedOutput`

### `src\pipelines\config.py`
_Pipeline configuration management._

**PipelineConfig**: `load(cls, project_path: Path) -> 'PipelineConfig', save(self, project_path: Path) -> None`

### `src\dispatch\handler.py`
_Unified task dispatch handling with mode detection._

**DispatchHandler**: `prepare(self, content: str, project_path: Path, cli: str, model: str | None) -> DispatchRequest, build_prompt(self, request: DispatchRequest, system_prompt: str) -> str, build_phase2_prompt(self, request: DispatchRequest, test_path: str, system_prompt: str) -> str | None, get_test_path(self, request: DispatchRequest) -> str | None`

### `src\mapper\mapper.py`
_Main codebase mapping logic._

**CodebaseMap**: `to_markdown(self) -> str`
**CodebaseMapper**: `map(self) -> CodebaseMap`

### `src\mapper\git_info.py`
_Git history and status extraction._

**RecentCommit**: `hash, message, files`
**GitInfoExtractor**: `get_recent_commits(self, project_path: Path, limit: int = 5) -> list[RecentCommit], get_uncommitted_changes(self, project_path: Path) -> list[str]`

### `src\specs\prompts.py`
_Prompt templates for spec-driven development._

**SpecPromptBuilder**: `build_phase1_prompt(self, spec: SpecDocument) -> str, build_phase2_prompt(self, spec: SpecDocument, test_path: str) -> str`

### `src\specs\runner.py`
_Orchestrates two-phase spec execution (test generation then implementation)._

**SpecPhaseRunner**: `get_phase1_request(self) -> PhaseRequest, complete_phase1(self, success: bool, test_path: str) -> None, get_phase2_request(self) -> PhaseRequest | None, infer_test_path(self) -> str`

### `src\git\operations.py`
**GitOperations**: `get_diff(self, project_path: Path) -> GitDiff, stage_all(self, project_path: Path) -> bool, commit(self, project_path: Path, message: str) -> CommitResult, push(self, project_path: Path, branch: str | None) -> bool, get_current_branch(self, project_path: Path) -> str | None`

### `src\mapper\parser.py`
_Python source file parser using AST._

**ModuleInfo**: `summary(self) -> str`
**PythonParser**: `parse(self, path: Path) -> ModuleInfo | None`

### `src\specs\parser.py`
_Parser for markdown spec format._

**SpecParser**: `parse(self, markdown: str) -> SpecDocument`

### `src\git\workflow.py`
**GitWorkflow**: `current_branch(self) -> str | None, run(self) -> WorkflowResult`

### `src\specs\contracts.py`
_Spec-driven development contracts and data structures._

**SpecDocument**: `to_prompt_context(self) -> str`
**SpecValidationResult**: `is_valid, spec, errors`

### `src\specs\validator.py`
_Spec validation logic._

**Functions**: `validate_spec(markdown: str) -> SpecValidationResult`

### `src\pipelines\runner.py`
_Pipeline execution engine._

**PipelineRunner**: `run_post_commit(self, diff: str) -> None`

### `src\mapper\detector.py`
_Stack and pattern detection from project files._

**StackDetector**: `detect(self, project_path: Path) -> StackInfo`

### `src\tasks\tracker.py`
_Task tracking for dispatched coding tasks._

**TaskTracker**: `create_task(self, project_path: str, cli: str) -> str, complete_task(self, task_id: str, files_modified: list[str], summary: str) -> None, fail_task(self, task_id: str, error: str) -> None, get_task(self, task_id: str) -> TaskRecord | None, get_recent_tasks(self, limit: int) -> list[TaskRecord]`

### `_claude_runner.py`

### `src\tasks\contracts.py`
_Data contracts for task tracking._

**TaskRecord**: `to_dict(self) -> dict, from_dict(cls, data: dict) -> 'TaskRecord'`

### `src\git\commit_message.py`
**CommitMessageGenerator**: `generate(self, diff: GitDiff) -> str`

### `src\git\contracts.py`

### `src\pipelines\auto_docs.py`
_Auto-documentation utilities._

**Functions**: `ensure_doc_structure(project_path: Path) -> None`

### `src\git\__init__.py`

### `src\specs\__init__.py`
_Spec-driven development module._


### `src\mapper\__init__.py`
_Codebase mapping for context-aware prompting._


### `src\__init__.py`
_Claude Desktop to Claude Code Bridge MCP Server._


### `src\pipelines\__init__.py`
_Post-commit pipeline execution module._


### `src\tasks\__init__.py`
_Task tracking module._



## Stats

- Files: 35
- Directories: 8
- Lines: 3835