"""write_command tool — run a single program directly, without a shell."""

import json
import os
import shutil
import subprocess
from pathlib import Path

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError

_BLOCKED: frozenset[str] = frozenset(
    {
        # shells
        "bash",
        "sh",
        "zsh",
        "dash",
        "fish",
        "ksh",
        "csh",
        "tcsh",
        # interpreters
        "python",
        "python3",
        "python2",
        "perl",
        "ruby",
        "node",
        "nodejs",
        "lua",
        "php",
        # escape hatches
        "env",
        "xargs",
        "sudo",
        "su",
        # read-only utilities (execute_bash handles these)
        "ls",
        "cat",
        "echo",
        "printf",
        "grep",
        "find",
        "head",
        "tail",
        "stat",
        # no-ops
        "true",
        "false",
    }
)


_TOOL_TAG = "shell::write"


def _colorize(msg: str) -> str:
    if os.environ.get("COLOR", "ascii") != "ascii":
        return msg
    red, reset = "\033[31m", "\033[0m"
    return f"{red}{msg}{reset}"


def register(mcp: FastMCP, *, blocklist: frozenset[str] = _BLOCKED) -> None:
    """Register the write_command tool with the MCP server."""

    async def write_command(
        command: str,
        ctx: Context,
        arguments: list[str] = [],
        working_dir: str | None = None,
        environment: dict[str, str] | None = None,
        summary: str | None = None,
    ) -> str:
        name = Path(command).name
        if name in blocklist:
            raise ToolError(f"write_command: {name!r} is not permitted")

        merged_env = os.environ.copy()
        if environment:
            merged_env.update({k: os.path.expandvars(v) for k, v in environment.items()})

        resolved = shutil.which(command, path=merged_env.get("PATH"))
        if resolved is None:
            raise ToolError(f"write_command: {command!r} not found in PATH")

        if Path(resolved).name in blocklist:
            raise ToolError(f"write_command: {command!r} is not permitted")

        cmd_str = " ".join([command] + arguments)
        if working_dir:
            rel = os.path.relpath(working_dir, os.getcwd())
            msg = f"I will run the following command: {cmd_str} (in {rel}) (using tool: {_colorize(_TOOL_TAG)})"
        else:
            msg = f"I will run the following command: {cmd_str} (using tool: {_colorize(_TOOL_TAG)})"

        if summary:
            msg += f"\nPurpose: {summary}"

        result = await ctx.elicit(message=msg, response_type=None)
        if result.action != "accept":
            raise ToolError("Tool use was cancelled by the user")

        proc = subprocess.run(
            [resolved] + arguments,
            capture_output=True,
            text=True,
            cwd=working_dir or None,
            env=merged_env,
        )
        return json.dumps(
            {
                "exit_status": str(proc.returncode),
                "stderr": proc.stderr,
                "stdout": proc.stdout,
            }
        )

    write_command.__doc__ = """\
Execute a single program directly (no shell) and return stdout, stderr, and exit status.

        Unlike read_bash, no shell interpretation occurs — pipes, redirects, and glob
        expansion are not supported. Use this tool only when the program must write into
        the workspace — modifying project files, applying migrations, etc. The workspace
        is write-protected during read_bash execution; use this tool to bypass that
        protection intentionally. If the program's purpose is to observe or verify state
        (tests, linters, build tools that only read source files), use read_bash even if
        it incidentally writes outside the workspace.

        Parameters
        ----------
          command      Executable name (e.g. "git", "npm") or absolute path. Resolved via
                       PATH after merging environment. The following commands are not
                       permitted: %s
          arguments    Positional arguments passed directly to the program (argv[1..]).
                       No shell expansion — each element is a literal argument.
          working_dir  Directory to run the command in (optional, default: cwd).
          environment  Additional environment variables merged over the process environment
                       (optional). Values support $VAR expansion. Affects PATH resolution
                       and is passed to the child process.
          summary      Human-readable description of what the command does (optional).

        Return value (JSON):
          { "exit_status": "0", "stdout": "...", "stderr": "..." }
          NOTE: exit_status is always a string, not an integer.

        Gotchas:
          - Shell features (pipes, &&, subshells) are not available — use execute_bash instead
          - A non-zero exit_status does NOT make the tool return is_error=True —
            always check exit_status explicitly

        Examples
        --------
          # Install a package
          {"command": "pip", "arguments": ["install", "requests"]}

          # Run git in a specific directory
          {"command": "git", "arguments": ["commit", "-m", "fix: typo"], "working_dir": "/code"}

          # Pass extra env vars
          {"command": "make", "arguments": ["build"], "environment": {"DEBUG": "1"}}

        """ % ", ".join(sorted(blocklist))

    mcp.tool(name="write_command")(write_command)
