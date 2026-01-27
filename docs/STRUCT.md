# ClaudeDesktop-ClaudeCode-Bridge

**Language:** python

## Structure

- `docs/` - Documentation (0 files)
- `src/` - Source code (0 files)
- `src/dispatch/` - Project files (0 files)
- `src/git/` - Project files (0 files)
- `src/mapper/` - Project files (0 files)
- `src/output/` - Project files (0 files)
- `src/pipelines/` - Project files (0 files)
- `src/specs/` - Project files (0 files)
- `src/tasks/` - Project files (0 files)
- `src/utils/` - Utilities (0 files)
- `tests/` - Tests (0 files)
- `tests/output/` - Project files (0 files)
- `tests/specs/` - Project files (0 files)

## Key Files

- `src\server.py` - Server entry
- `src\pipelines\config.py` - Configuration
- `src\git\contracts.py` - Data contracts
- `src\specs\contracts.py` - Data contracts
- `src\tasks\contracts.py` - Data contracts
- `pyproject.toml` - Project config
- `README.md` - Documentation

## Module Details

### `src\server.py`
**DispatchGuard**: check_running_task, check_duplicate, record_dispatch
**ClaudeCodeMCPServer**: run
**Functions**: `main()`

### `src\pipelines\config.py`
_Pipeline configuration management._

**PipelineConfig**: load, save

### `src\specs\contracts.py`
_Spec-driven development contracts and data structures._

**SpecDocument**: to_prompt_context

### `src\tasks\contracts.py`
_Data contracts for task tracking._

**TaskRecord**: to_dict, from_dict


## Entry Points

- **New test:** tests/

## Stats

- Files: 7
- Directories: 13
- Lines: 973