import json
import pytest
from datetime import datetime

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from server import ClaudeCodeMCPServer


@pytest.fixture
def server() -> ClaudeCodeMCPServer:
    return ClaudeCodeMCPServer()


class TestHealthCheck:
    def test_health_check_returns_ok_status(self, server: ClaudeCodeMCPServer) -> None:
        result = server._handle_health_check({})
        data = json.loads(result[0].text)
        assert data["status"] == "ok"

    def test_health_check_returns_timestamp(self, server: ClaudeCodeMCPServer) -> None:
        result = server._handle_health_check({})
        data = json.loads(result[0].text)
        assert "timestamp" in data
        datetime.fromisoformat(data["timestamp"])

    def test_health_check_returns_version(self, server: ClaudeCodeMCPServer) -> None:
        result = server._handle_health_check({})
        data = json.loads(result[0].text)
        assert data["version"] == "1.0.0"

    def test_health_check_with_empty_arguments(self, server: ClaudeCodeMCPServer) -> None:
        result = server._handle_health_check({})
        data = json.loads(result[0].text)
        assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_health_check_tool_registered(server: ClaudeCodeMCPServer) -> None:
    tools = await server._list_tools()
    tool_names = [t.name for t in tools]
    assert "health_check" in tool_names
