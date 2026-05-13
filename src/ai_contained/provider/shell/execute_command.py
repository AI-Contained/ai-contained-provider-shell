"""execute_command tool — run a single program directly, without a shell."""

from fastmcp import FastMCP

_BLOCKED: frozenset[str] = frozenset(
    {
        # shells
        "bash", "sh", "zsh", "dash", "fish", "ksh", "csh", "tcsh",
        # interpreters
        "python", "python3", "python2", "perl", "ruby", "node", "nodejs", "lua", "php",
        # escape hatches
        "env", "xargs", "sudo", "su",
        # read-only utilities (execute_bash handles these)
        "ls", "cat", "echo", "printf", "grep", "find", "head", "tail", "stat",
        # no-ops
        "true", "false",
    }
)


def register(mcp: FastMCP, *, blocklist: frozenset[str] = _BLOCKED) -> None:
    """Register the execute_command tool with the MCP server."""

    @mcp.tool(name="execute_command")
    async def execute_command(
        command: str,
        arguments: list[str],
        working_dir: str | None = None,
        environment: dict[str, str] | None = None,
        summary: str | None = None,
    ) -> str:
        """Execute a single program directly (no shell)."""
        raise NotImplementedError
