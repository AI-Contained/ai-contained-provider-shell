import os
import pytest
from fastmcp import FastMCP
from fastmcp.client.elicitation import ElicitResult

from ai_contained.provider.shell import register

@pytest.fixture
def mcp() -> FastMCP:
    server = FastMCP("test")
    register(server)
    return server


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """Isolated temp directory, chdir'd into for each test. Returns root as pathlib.Path."""
    root = tmp_path / "root"
    root.mkdir()
    monkeypatch.chdir(root)
    return root


def make_capture_handler():
    messages = []
    async def handler(message, response_type, params, context):
        messages.append(message)
        return ElicitResult(action="accept", content={"value": "y"})
    handler.messages = messages
    return handler


def make_decline_handler():
    messages = []
    async def handler(message, response_type, params, context):
        messages.append(message)
        return ElicitResult(action="decline", content=None)
    handler.messages = messages
    return handler
