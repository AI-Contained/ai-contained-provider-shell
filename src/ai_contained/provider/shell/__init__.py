"""Shell provider."""

from fastmcp import FastMCP

from ai_contained.provider.shell.execute_bash import register as _register_execute_bash


def register(mcp: FastMCP) -> None:
    _register_execute_bash(mcp)
