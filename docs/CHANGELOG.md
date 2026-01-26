# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

- 2026-01-26: feat: implement `DispatchGuard` to prevent duplicate and concurrent task dispatches
- 2026-01-26: refactor: update system prompt with stricter code size and refactoring standards
- 2026-01-26: feat: include full CLI output in task results and TaskTracker
- 2026-01-26: docs: remove deprecated git context sections from codebase manifest for performance
- 2026-01-26: refactor: optimize `CodebaseMapper` for high performance (<1s) using shallow walks and fast key-file identification
- 2026-01-26: feat: improve GUI task lifecycle with status reporting, summary display, and automatic git commit on success
- 2026-01-26: refactor: update `claude` CLI command to use `--permission-mode dontAsk`
- 2026-01-26: fix: add fallback mechanism and 5s timeout to commit message generator for better resilience
- 2026-01-26: refactor: remove legacy TwoPhaseSpecDispatch in favor of modular SpecPhaseRunner
- 2026-01-26: feat: implement two-phase spec execution (test generation then implementation)
- 2026-01-26: feat: add `.claude/steering.md` generation with project standards and stack info
- 2026-01-26: feat: implement CIRCUIT BREAKER in spec prompts to prevent excessive codebase exploration
- 2026-01-26: refactor: use relative imports in `src/output`
- 2026-01-26: docs: update documentation to reflect latest spec validation and output compression features
- 2026-01-26: feat: add `SpecValidationResult` and `validate_spec` for robust specification verification
- 2026-01-26: feat: enhance spec prompt to prioritize specification accuracy and minimize unnecessary codebase exploration
- 2026-01-26: feat: unify `launch_claude_code` and `dispatch_with_spec` into a single `dispatch` tool with auto-mode detection
- 2026-01-26: docs: update API and Architecture docs to reflect new CodebaseMapper capabilities
- 2026-01-26: refactor: replace `Assimilator` with `CodebaseMapper` and remove `src/assimilator/` module
- 2026-01-26: feat: add `dispatch_with_spec` tool for TDD-driven task execution
- 2026-01-26: fix: improve pipeline agent dispatch reliability using temporary files and shell pipes

### Added
- Codebase assimilator for compressed project manifests
- `get_manifest` MCP tool for instant codebase knowledge
- `get_task_result` MCP tool for task completion results
- `list_recent_tasks` MCP tool for recent dispatch history
- `dispatch_assimilate` MCP tool for background analysis
- Task tracking with persistent storage
- Post-commit auto-documentation pipeline
- Parallel file parsing for faster analysis
- Quick mode for rapid shallow analysis

### Changed
- `launch_claude_code` now returns task_id for tracking
- GUI viewer reports completion to task tracker

## [1.0.0] - 2025-01-25

### Added
- Initial MCP server with `launch_claude_code` tool
- Multi-CLI support: Claude Code, Gemini CLI, OpenAI Codex
- Real-time streaming GUI viewer
- Auto git commits with Ollama-generated messages
- Godot project validation integration
