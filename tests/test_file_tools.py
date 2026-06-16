from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from server import ClaudeCodeMCPServer


@pytest.fixture
def server() -> ClaudeCodeMCPServer:
    return ClaudeCodeMCPServer()


def test_read_file_supports_one_based_start_line(
    server: ClaudeCodeMCPServer, tmp_path: Path
) -> None:
    target = tmp_path / "example.txt"
    target.write_text("alpha\nbravo\ncharlie\n", encoding="utf-8")

    result = server._handle_read_file({
        "path": str(target),
        "start_line": 2,
        "limit": 1,
    })

    assert "lines 2-2" in result[0].text
    assert "use offset=2 for more" in result[0].text
    assert "   2  bravo" in result[0].text
    assert "alpha" not in result[0].text


def test_read_file_expands_environment_variables(
    server: ClaudeCodeMCPServer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "example.txt"
    target.write_text("alpha\n", encoding="utf-8")
    monkeypatch.setenv("MCP_READ_TEST_FILE", str(target))

    result = server._handle_read_file({"path": "%MCP_READ_TEST_FILE%"})

    assert "   1  alpha" in result[0].text


def test_read_file_pages_with_next_offset(
    server: ClaudeCodeMCPServer, tmp_path: Path
) -> None:
    target = tmp_path / "example.txt"
    target.write_text("\n".join(f"line-{i}" for i in range(1, 6)), encoding="utf-8")

    result = server._handle_read_file({
        "path": str(target),
        "offset": 1,
        "limit": 2,
    })

    assert "lines 2-3" in result[0].text
    assert "use offset=3 for more" in result[0].text
    assert "   2  line-2" in result[0].text
    assert "   3  line-3" in result[0].text


def test_read_file_rejects_invalid_pagination(
    server: ClaudeCodeMCPServer, tmp_path: Path
) -> None:
    target = tmp_path / "example.txt"
    target.write_text("alpha\n", encoding="utf-8")

    negative_offset = server._handle_read_file({"path": str(target), "offset": -1})
    zero_limit = server._handle_read_file({"path": str(target), "limit": 0})
    zero_start_line = server._handle_read_file({"path": str(target), "start_line": 0})

    assert negative_offset[0].text == "Invalid offset: must be >= 0"
    assert zero_limit[0].text == "Invalid limit: must be >= 1"
    assert zero_start_line[0].text == "Invalid start_line: must be >= 1"


def test_read_file_reports_binary_files(
    server: ClaudeCodeMCPServer, tmp_path: Path
) -> None:
    target = tmp_path / "image.bin"
    target.write_bytes(b"\x89PNG\r\n\x00\x00")

    result = server._handle_read_file({"path": str(target)})

    assert result[0].text == f"Binary file not displayed: {target}"


def test_search_files_skips_binary_files(
    server: ClaudeCodeMCPServer, tmp_path: Path
) -> None:
    (tmp_path / "text.txt").write_text("needle\n", encoding="utf-8")
    (tmp_path / "binary.bin").write_bytes(b"needle\x00")

    result = server._handle_search_files({"path": str(tmp_path), "pattern": "needle"})

    assert "text.txt:1: needle" in result[0].text
    assert "binary.bin" not in result[0].text
