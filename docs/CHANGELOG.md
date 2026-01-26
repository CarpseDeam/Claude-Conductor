# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

- 2026-01-26: docs: update STRUCT.md to include output masking components
- 2026-01-26: feat: implement output compression for spec validation to reduce context bloat
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
