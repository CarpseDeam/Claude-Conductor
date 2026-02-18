"""JSON stream parsing → HTML segments for Claude and Gemini CLI output."""
import json
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from output.masker import mask_output, CommandType
from gui.theme import COLORS


class SegmentType(Enum):
    TEXT = "text"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    SYSTEM = "system"
    ERROR = "error"


@dataclass
class FormattedSegment:
    html: str
    segment_type: SegmentType


def _c(key: str) -> str:
    return COLORS[key]


def _span(text: str, color: str) -> str:
    safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f"<span style='color:{color};'>{safe}</span>"


def _badge(label: str, color: str) -> str:
    return (
        f"<span style='background:{_c('badge_bg')}; color:{color}; "
        f"padding:2px 8px; border-radius:3px; font-size:12px; font-weight:bold;'>{label}</span>"
    )


def _apply_inline_markdown(text: str) -> str:
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(
        r"`([^`]+)`",
        lambda m: f"<code style='background:{_c('badge_bg')}; padding:1px 4px; border-radius:2px;'>{m.group(1)}</code>",
        text,
    )
    return text


def _seg(html: str, kind: SegmentType = SegmentType.TEXT) -> FormattedSegment:
    return FormattedSegment(html=html, segment_type=kind)


def _tool_badge_html(label: str, color: str, detail: str) -> str:
    return _badge(label, color) + " " + _span(detail, _c("text_muted")) + "<br>"


def format_tool_badge(tool: str, detail: str) -> str:
    label, color = _tool_label_color(tool)
    return _tool_badge_html(label, color, detail)


def _tool_label_color(tool: str) -> tuple[str, str]:
    if tool in ("Read", "read_file"):
        return "READ", _c("accent_blue")
    if tool in ("Write", "Edit", "MultiEdit", "write_file"):
        return "EDIT", _c("accent_yellow")
    if tool in ("Bash", "run_shell_command", "Shell"):
        return "BASH", _c("accent_yellow")
    if tool in ("Glob", "Grep", "FindFiles", "SearchText"):
        return "SEARCH", _c("accent_cyan")
    if tool in ("LS", "list_directory", "ReadFolder"):
        return "LS", _c("accent_cyan")
    if tool in ("TodoWrite", "WriteTodos", "write_todos"):
        return "TODO", _c("accent_magenta")
    return tool.upper()[:8], _c("accent_yellow")


def _get_tool_type(tool: str) -> str:
    if tool in ("Read", "read_file"):
        return "read"
    if tool in ("Write", "Edit", "MultiEdit", "write_file"):
        return "write"
    if tool in ("Bash", "run_shell_command", "Shell"):
        return "bash"
    return "other"


def _detect_command_type(cmd: str) -> CommandType | None:
    cmd_lower = cmd.lower().strip()
    if cmd_lower.startswith("pytest") or " -m pytest" in cmd_lower:
        return CommandType.PYTEST
    if cmd_lower.startswith("mypy") or " -m mypy" in cmd_lower:
        return CommandType.MYPY
    if any(cmd_lower.startswith(x) for x in ("ruff", "flake8")) or "lint" in cmd_lower:
        return CommandType.LINT
    return None


def _format_tool_call_html(tool: str, inp: dict, stats: dict, state: dict) -> list[FormattedSegment]:
    segs = []
    tool_type = _get_tool_type(tool)
    if tool_type != state.get("last_tool_type") and state.get("last_tool_type") is not None:
        segs.append(_seg("<br>"))
    state["last_tool_type"] = tool_type

    if tool in ("Read", "read_file"):
        path = inp.get("file_path") or inp.get("path", "")
        filename = Path(path).name if path else "?"
        if path and path not in stats["files_read"]:
            stats["files_read"].append(path)
        segs.append(_seg(_tool_badge_html("READ", _c("accent_blue"), filename), SegmentType.TOOL_CALL))

    elif tool in ("Write", "Edit", "MultiEdit", "write_file"):
        path = inp.get("file_path") or inp.get("path", "")
        filename = Path(path).name if path else "?"
        if path and path not in stats["files_written"]:
            stats["files_written"].append(path)
        segs.append(_seg(_tool_badge_html("EDIT", _c("accent_yellow"), filename), SegmentType.TOOL_CALL))

    elif tool in ("Bash", "run_shell_command", "Shell"):
        cmd = inp.get("command", "")
        state["last_bash_command"] = cmd
        segs.append(_seg(_tool_badge_html("BASH", _c("accent_yellow"), cmd[:80]), SegmentType.TOOL_CALL))

    elif tool in ("Glob", "Grep", "FindFiles", "SearchText"):
        pattern = inp.get("pattern", "")[:60]
        segs.append(_seg(_tool_badge_html("SEARCH", _c("accent_cyan"), pattern), SegmentType.TOOL_CALL))

    elif tool in ("LS", "list_directory", "ReadFolder"):
        path = (inp.get("dir_path") or inp.get("path", "."))[:40]
        segs.append(_seg(_tool_badge_html("LS", _c("accent_cyan"), path), SegmentType.TOOL_CALL))

    elif tool in ("TodoWrite", "WriteTodos", "write_todos"):
        segs.append(_seg(format_todo_list(inp.get("todos", [])), SegmentType.TOOL_CALL))

    else:
        detail = inp.get("command", inp.get("path", ""))[:60]
        label, color = _tool_label_color(tool)
        segs.append(_seg(_tool_badge_html(label, color, detail), SegmentType.TOOL_CALL))

    return segs


def _format_result_html(result_content: str, is_error: bool, last_bash: str | None, stats: dict, state: dict) -> list[FormattedSegment]:
    cmd_type = _detect_command_type(last_bash) if last_bash else None
    if cmd_type:
        masked = mask_output(result_content, cmd_type)
        state["last_bash_command"] = None
        if is_error or masked.errors:
            stats["errors"] += 1
            html = _badge("FAILED", _c("accent_red")) + " " + _span(masked.summary, _c("accent_red")) + "<br>"
            return [_seg(html, SegmentType.ERROR)]
        html = _badge("OK", _c("accent_green")) + " " + _span(masked.summary, _c("text_muted")) + "<br>"
        return [_seg(html, SegmentType.TOOL_RESULT)]

    max_len = 400 if is_error else 150
    content = result_content[:max_len].replace("\n", " ").strip()
    if is_error:
        stats["errors"] += 1
        html = _badge("FAILED", _c("accent_red")) + " " + _span(content, _c("accent_red")) + "<br>"
        return [_seg(html, SegmentType.ERROR)]

    preview = content[:100] + "..." if len(content) > 100 else content
    html = _badge("OK", _c("accent_green")) + (" " + _span(preview, _c("text_muted")) if preview else "") + "<br>"
    return [_seg(html, SegmentType.TOOL_RESULT)]


def format_claude_line(line: str, stats: dict, state: dict) -> list[FormattedSegment]:
    try:
        data = json.loads(line)
    except json.JSONDecodeError:
        return [_seg(_apply_inline_markdown(line) + "<br>")] if line.strip() else []

    msg_type = data.get("type", "")

    if msg_type == "system":
        session = data.get("session_id", "")[:8]
        return [_seg(_span(f"[Session: {session}...]", _c("text_muted")) + "<br>", SegmentType.SYSTEM)]

    if msg_type == "stream_event":
        return _handle_stream_event(data, stats)

    if msg_type == "assistant":
        content = data.get("message", {}).get("content", [])
        segs = []
        for block in content:
            if block.get("type") == "tool_use":
                stats["tools_used"] += 1
                segs.extend(_format_tool_call_html(block["name"], block.get("input", {}), stats, state))
        return segs

    if msg_type == "user":
        return _handle_claude_tool_results(data, stats, state)

    if msg_type == "result":
        return [_seg("<br>")]

    return []


def _handle_stream_event(data: dict, stats: dict) -> list[FormattedSegment]:
    event = data.get("event", {})
    event_type = event.get("type", "")

    if event_type == "content_block_delta":
        delta = event.get("delta", {})
        if delta.get("type") == "text_delta":
            text = delta.get("text", "")
            return [_seg(_apply_inline_markdown(text))]
        return []

    if event_type == "content_block_start":
        block = event.get("content_block", {})
        if block.get("type") == "tool_result":
            is_error = block.get("is_error", False)
            content = block.get("content", "")[:400 if is_error else 200]
            if is_error:
                stats["errors"] += 1
                html = "<br>" + _badge("ERROR", _c("accent_red")) + " " + _span(content, _c("accent_red")) + "<br>"
                return [_seg(html, SegmentType.ERROR)]
            html = _badge("OK", _c("accent_green")) + " " + _span(content[:80] + "...", _c("text_muted")) + "<br>"
            return [_seg(html, SegmentType.TOOL_RESULT)]

    if event_type == "message_start":
        model = event.get("message", {}).get("model", "")
        if model:
            return [_seg(_span(f"[Model: {model}]", _c("text_muted")) + "<br><br>", SegmentType.SYSTEM)]

    return []


def _handle_claude_tool_results(data: dict, stats: dict, state: dict) -> list[FormattedSegment]:
    content = data.get("message", {}).get("content", [])
    segs = []
    for block in content:
        if block.get("type") != "tool_result":
            continue
        is_error = block.get("is_error", False)
        result_content = block.get("content", "")
        if isinstance(result_content, list):
            result_content = str(result_content[0].get("text", ""))
        else:
            result_content = str(result_content)
        segs.extend(_format_result_html(result_content, is_error, state.get("last_bash_command"), stats, state))
    return segs


def format_gemini_line(line: str, stats: dict, state: dict) -> list[FormattedSegment]:
    try:
        data = json.loads(line)
    except json.JSONDecodeError:
        return [_seg(_apply_inline_markdown(line) + "<br>")] if line.strip() else []

    msg_type = data.get("type", "")

    if msg_type == "init":
        session = data.get("session_id", "")[:8]
        model = data.get("model", "")
        text = f"[Session: {session}... | Model: {model}]"
        return [_seg(_span(text, _c("text_muted")) + "<br>", SegmentType.SYSTEM)]

    if msg_type == "tool_use":
        tool = data.get("tool_name", "?")
        inp = data.get("parameters", {}) or data.get("input", {})
        stats["tools_used"] += 1
        if tool in ("Bash", "run_shell_command", "Shell"):
            state["last_bash_command"] = inp.get("command", "")
        return _format_tool_call_html(tool, inp, stats, state)

    if msg_type == "tool_result":
        status = data.get("status", "success")
        is_error = status == "error" or data.get("is_error", False)
        output = data.get("output", "")
        result_content = output if isinstance(output, str) else str(output)
        return _format_result_html(result_content, is_error, state.get("last_bash_command"), stats, state)

    if msg_type == "message":
        if data.get("role") == "assistant":
            content = data.get("content", "")
            if content:
                return [_seg(_apply_inline_markdown(content) + "<br>")]

    return []


def format_todo_list(todos: list) -> str:
    if not todos:
        return ""
    border_color = _c("text_dimmed")
    lines = [f"<div style='border-left:2px solid {border_color}; margin:4px 0; padding-left:8px;'>"]
    lines.append(_span("TODO LIST", _c("accent_magenta")) + "<br>")
    for t in todos:
        status = t.get("status", "pending")
        content = t.get("content", "")[:60]
        if status == "completed":
            icon, color = "✓", _c("accent_green")
        elif status == "in_progress":
            icon, color = "►", _c("accent_yellow")
        else:
            icon, color = "○", _c("text_muted")
        lines.append(_span(f"{icon} {content}", color) + "<br>")
    lines.append("</div>")
    return "".join(lines)


def format_turn_separator(turn_number: int) -> str:
    """HTML divider between session turns."""
    return (
        f"<br><div style='border-top:1px solid {_c('border')}; margin:12px 0; padding-top:10px;'>"
        f"<span style='color:{_c('accent_magenta')}; font-weight:bold; font-size:12px;'>"
        f"Turn {turn_number}</span></div>"
    )


def format_summary_card(stats: dict) -> str:
    import time
    duration = int(time.time() - stats["start_time"])
    files_read = len(stats["files_read"])
    files_written = stats["files_written"]
    tools_used = stats["tools_used"]
    errors = stats["errors"]

    modified_names = ", ".join(Path(f).name for f in files_written[:5])
    if len(files_written) > 5:
        modified_names += f", +{len(files_written) - 5} more"

    error_color = _c("accent_red") if errors > 0 else _c("accent_green")
    written_color = _c("accent_green") if files_written else _c("text_primary")

    lines = [
        f"<div style='background:{_c('bg_secondary')}; border:1px solid {_c('border')}; "
        f"border-radius:6px; padding:12px 16px; margin:8px 0;'>",
        f"<div style='color:{_c('accent_blue')}; font-weight:bold; margin-bottom:8px;'>Summary</div>",
        f"<div style='color:{_c('text_primary')};'>Duration: {duration}s</div>",
        f"<div style='color:{_c('text_primary')};'>Files read: {files_read}</div>",
        f"<div style='color:{written_color};'>Files modified: {len(files_written)}"
        + (f" ({modified_names})" if files_written else "") + "</div>",
        f"<div style='color:{_c('text_primary')};'>Tool calls: {tools_used}</div>",
        f"<div style='color:{error_color};'>Errors: {errors}</div>",
        "</div>",
    ]
    return "".join(lines)
