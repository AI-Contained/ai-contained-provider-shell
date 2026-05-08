"""Shell provider."""

from fastmcp import FastMCP

from ai_contained.provider.shell.execute_bash import register as _register_execute_bash


def register(mcp: FastMCP) -> None:
    """Register all shell provider tools with the MCP server."""
    _register_execute_bash(mcp)
