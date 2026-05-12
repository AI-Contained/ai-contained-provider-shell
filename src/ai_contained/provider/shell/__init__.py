"""Shell provider."""

from fastmcp import FastMCP

from ai_contained.provider.shell.execute_bash import register as _register_execute_bash
from ai_contained.provider.shell.execute_command import register as _register_execute_command


def register(mcp: FastMCP) -> None:
    """Register all shell provider tools with the MCP server."""
    _register_execute_bash(mcp)
    _register_execute_command(mcp)
