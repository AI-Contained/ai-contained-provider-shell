"""read_bash tool — run shell commands."""

import json
import os
import shutil
import subprocess

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError

_TOOL_TAG = "shell::read"


def register(mcp: FastMCP) -> None:
    """Register the read_bash tool with the MCP server."""

    @mcp.tool(name="read_bash")
    async def read_bash(  # noqa: D417
        command: str,
        ctx: Context,
        working_dir: str | None = None,
        summary: str | None = None,
    ) -> str:
        """Run a read-only bash command and return stdout, stderr, and exit status.

        Parameters
        ----------
          command      Bash command to execute (required). Supports shell features:
                       pipes, redirects, &&, ;, subshells, etc.
          working_dir  Directory to run the command in (optional, default: cwd).
                       Shown in the elicitation as a path relative to cwd.
          summary      Human-readable description of what the command does (optional).
                       Not currently shown in the elicitation message.

        Return value (JSON):
          { "exit_status": "0", "stdout": "...", "stderr": "..." }
          NOTE: exit_status is always a string, not an integer.

        Gotchas:
          - Both stdout and stderr are captured independently — a command can produce
            both simultaneously (e.g. ls with one valid and one invalid path)
          - A non-zero exit_status does NOT make the tool return is_error=True —
            always check exit_status explicitly
          - working_dir is shown relative to cwd in the elicitation, e.g.
            /code/volatile → "volatile", /tmp → "../tmp"

        Examples
        --------
          # Simple command
          {"command": "echo hello"}

          # Run in a specific directory
          {"command": "ls -la", "working_dir": "/code/src"}

          # Capture both stdout and stderr
          {"command": "ls valid_file /nonexistent"}

        """
        if working_dir:
            rel = os.path.relpath(working_dir, os.getcwd())
            msg = f"I will run the following command: {command} (in {rel}) (using tool: {_TOOL_TAG})"
        else:
            msg = f"I will run the following command: {command} (using tool: {_TOOL_TAG})"

        if summary:
            msg += f"\nPurpose: {summary}"

        # elicit (skipped when EXPERIMENTAL_ALLOW_ALL_READS is set)
        if not os.environ.get("EXPERIMENTAL_APPROVE_ALL_READS"):
            result = await ctx.elicit(message=msg, response_type=None)
            if result.action != "accept":
                raise ToolError("Tool use was cancelled by the user")

        downgrade_exec = (
            os.environ.get("DOWNGRADE_EXEC") or shutil.which("downgrade_exec") or "/usr/local/bin/downgrade_exec"
        )
        downgrade_args = os.environ.get("DOWNGRADE_ARGS", "--check=writable").split()
        proc = subprocess.run(
            [downgrade_exec, *downgrade_args, "--", "/bin/sh", "-c", command],
            capture_output=True,
            text=True,
            cwd=working_dir or None,
        )
        return json.dumps(
            {
                "exit_status": str(proc.returncode),
                "stderr": proc.stderr,
                "stdout": proc.stdout,
            }
        )
