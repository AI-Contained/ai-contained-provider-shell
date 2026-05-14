"""Shell provider."""

from fastmcp import FastMCP

from ai_contained.provider.shell.read_bash import register as _register_read_bash
from ai_contained.provider.shell.write_command import register as _register_write_command


def register(mcp: FastMCP) -> None:
    """Register all shell provider tools with the MCP server."""
    _register_read_bash(mcp)
    _register_write_command(mcp)
