"""execute_command tool — run a single program directly, without a shell."""

from fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
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
