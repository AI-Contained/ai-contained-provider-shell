"""execute_bash tool — run shell commands."""

import json
import os
import subprocess

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError


def register(mcp: FastMCP) -> None:

    @mcp.tool(name="execute_bash")
    async def execute_bash(
        command: str,
        ctx: Context,
        working_dir: str | None = None,
        summary: str | None = None,
    ) -> str:
        """Execute a bash command and return stdout, stderr, and exit status.

        Parameters:
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

        Examples:
          # Simple command
          {"command": "echo hello"}

          # Run in a specific directory
          {"command": "ls -la", "working_dir": "/code/src"}

          # Capture both stdout and stderr
          {"command": "ls valid_file /nonexistent"}
        """
        if working_dir:
            rel = os.path.relpath(working_dir, os.getcwd())
            msg = f"I will run the following command: {command} (in {rel}) (using tool: shell)"
        else:
            msg = f"I will run the following command: {command} (using tool: shell)"

        if summary:
            msg += f"\nPurpose: {summary}"

        result = await ctx.elicit(message=msg, response_type=None)
        if result.action != "accept":
            raise ToolError("Tool use was cancelled by the user")

        proc = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            cwd=working_dir or None,
        )
        return json.dumps({
            "exit_status": str(proc.returncode),
            "stderr": proc.stderr,
            "stdout": proc.stdout,
        })
