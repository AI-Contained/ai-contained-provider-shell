"""Shell provider."""
from ai_contained.provider.shell.execute_bash import register as _register_execute_bash


def register(mcp):
    _register_execute_bash(mcp)
