import os
from collections.abc import AsyncGenerator, Callable, Coroutine, Generator
from pathlib import Path
from typing import Any

import pytest
from assertpy import assert_that  # type: ignore[import-untyped]
from fastmcp import FastMCP
from fastmcp.client import Client
from fastmcp.client.transports import FastMCPTransport
from mcp.types import TextContent

from ai_contained.core.mcp.testing import Elicitor, WrapCallToolResult
from ai_contained.provider.shell.execute_command import _BLOCKED
from ai_contained.provider.shell.execute_command import register as register_execute_command

ExecuteCommand = Callable[..., Coroutine[Any, Any, WrapCallToolResult]]


def assert_command_prompt(
    command: str,
    arguments: list[str],
    working_dir: str | None = None,
    summary: str | None = None,
) -> str:
    cmd_str = " ".join([command] + arguments)
    if working_dir:
        rel = os.path.relpath(working_dir)
        msg = f"I will run the following command: {cmd_str} (in {rel}) (using tool: shell)"
    else:
        msg = f"I will run the following command: {cmd_str} (using tool: shell)"
    if summary:
        msg += f"\nPurpose: {summary}"
    return msg


def describe_execute_command() -> None:

    @pytest.fixture
    def elicitor() -> Generator[Elicitor, None, None]:
        e = Elicitor()
        yield e
        assert not e._queue, f"{len(e._queue)} elicitation step(s) were never triggered"

    @pytest.fixture
    async def client(elicitor: Elicitor) -> AsyncGenerator[Client[FastMCPTransport], None]:
        """Production client — real blocklist enforced."""
        server = FastMCP("test")
        register_execute_command(server)
        async with Client(transport=server, elicitation_handler=elicitor) as c:
            yield c

    @pytest.fixture
    async def client_any_command(elicitor: Elicitor) -> AsyncGenerator[Client[FastMCPTransport], None]:
        """Test client — no blocklist, allows any command including ls/cat."""
        server = FastMCP("test")
        register_execute_command(server, blocklist=frozenset())
        async with Client(transport=server, elicitation_handler=elicitor) as c:
            yield c

    @pytest.fixture
    def execute_command(client_any_command: Client[FastMCPTransport], elicitor: Elicitor) -> ExecuteCommand:
        async def _run(
            command: str,
            arguments: list[str] | None = None,
            *,
            working_dir: str | None = None,
            environment: dict[str, str] | None = None,
            summary: str | None = None,
            raise_on_error: bool = True,
        ) -> WrapCallToolResult:
            if arguments is None:
                arguments = []
            elicitor.accept(
                expect_message=assert_command_prompt(command, arguments, working_dir=working_dir, summary=summary)
            )
            args: dict[str, Any] = {"command": command, "arguments": arguments}
            if working_dir:
                args["working_dir"] = working_dir
            if environment is not None:
                args["environment"] = environment
            if summary:
                args["summary"] = summary
            return WrapCallToolResult(
                **vars(await client_any_command.call_tool("execute_command", args, raise_on_error=raise_on_error))
            )

        return _run

    def describe_basic_execution() -> None:
        async def it_runs_a_command_and_returns_stdout(execute_command: ExecuteCommand, tmp_path: Path) -> None:
            (tmp_path / "hello.txt").write_text("world\n")
            result = await execute_command("cat", [str(tmp_path / "hello.txt")])
            assert_that(result.is_error).is_false()
            assert_that(result.json()).is_equal_to({"exit_status": "0", "stdout": "world\n", "stderr": ""})

        async def it_captures_stderr(execute_command: ExecuteCommand) -> None:
            result = await execute_command("ls", ["/nonexistent_xyz_abc_123"])
            assert_that(result.is_error).is_false()
            assert_that(result.json()["exit_status"]).is_not_equal_to("0")
            assert_that(result.json()["stderr"]).is_not_empty()

        async def it_captures_both_stdout_and_stderr(execute_command: ExecuteCommand, tmp_path: Path) -> None:
            (tmp_path / "hello.txt").write_text("world\n")
            result = await execute_command("ls", [str(tmp_path), "/nonexistent_xyz_abc_123"])
            assert_that(result.is_error).is_false()
            assert_that(result.json()["stdout"]).is_not_empty()
            assert_that(result.json()["stderr"]).is_not_empty()

        async def it_returns_exit_status_as_string_not_int(execute_command: ExecuteCommand) -> None:
            result = await execute_command("ls", ["/tmp"])
            assert_that(result.json()["exit_status"]).is_instance_of(str)

        async def it_returns_nonzero_exit_status(execute_command: ExecuteCommand) -> None:
            result = await execute_command("ls", ["/nonexistent_xyz_abc_123"])
            assert_that(result.is_error).is_false()
            assert_that(result.json()["exit_status"]).is_not_equal_to("0")

    def describe_arguments() -> None:
        async def it_passes_arguments_to_command(execute_command: ExecuteCommand, tmp_path: Path) -> None:
            (tmp_path / "hello.txt").write_text("world\n")
            result = await execute_command("cat", [str(tmp_path / "hello.txt")])
            assert_that(result.json()).is_equal_to({"exit_status": "0", "stdout": "world\n", "stderr": ""})

        async def it_does_not_expand_shell_globs(execute_command: ExecuteCommand, tmp_path: Path) -> None:
            # a shell would expand *.txt — direct exec passes the literal string
            result = await execute_command("ls", [str(tmp_path / "*.txt")])
            assert_that(result.json()["exit_status"]).is_not_equal_to("0")
            assert_that(result.json()["stderr"]).contains("*.txt")

    def describe_blocklist() -> None:
        @pytest.mark.parametrize("blocked", sorted(_BLOCKED))
        async def it_rejects_blocked_commands(
            client: Client[FastMCPTransport], blocked: str
        ) -> None:
            result = await client.call_tool(
                "execute_command", {"command": blocked, "arguments": []}, raise_on_error=False
            )
            assert_that(result.is_error).is_true()
            assert isinstance(result.content[0], TextContent)
            assert_that(result.content[0].text).contains(blocked)

        async def it_rejects_before_elicitation(
            client: Client[FastMCPTransport], elicitor: Elicitor
        ) -> None:
            # elicitor queue stays empty — rejection happens before elicitation
            result = await client.call_tool(
                "execute_command", {"command": "bash", "arguments": []}, raise_on_error=False
            )
            assert_that(result.is_error).is_true()

    def describe_path_resolution() -> None:
        async def it_resolves_command_via_path(execute_command: ExecuteCommand) -> None:
            result = await execute_command("ls", ["/tmp"])
            assert_that(result.json()["exit_status"]).is_equal_to("0")

        async def it_rejects_unknown_command(client_any_command: Client[FastMCPTransport]) -> None:
            result = await client_any_command.call_tool(
                "execute_command",
                {"command": "nonexistent_command_xyz_abc", "arguments": []},
                raise_on_error=False,
            )
            assert_that(result.is_error).is_true()
            assert isinstance(result.content[0], TextContent)
            assert_that(result.content[0].text).contains("nonexistent_command_xyz_abc")

    def describe_working_dir() -> None:
        @pytest.fixture
        def sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[Path, None, None]:
            root = tmp_path / "root"
            root.mkdir()
            monkeypatch.chdir(root)
            yield root

        async def it_runs_in_specified_working_dir(execute_command: ExecuteCommand, sandbox: Path) -> None:
            subdir = sandbox / "work"
            subdir.mkdir()
            result = await execute_command("pwd", working_dir=str(subdir))
            assert_that(result.json()).is_equal_to({"exit_status": "0", "stdout": f"{subdir}\n", "stderr": ""})

        async def it_shows_relative_path_in_elicitation(execute_command: ExecuteCommand, sandbox: Path) -> None:
            # assert_command_prompt uses os.path.relpath — elicitor validates the message matches
            result = await execute_command("pwd", working_dir="/tmp")
            assert_that(result.json()["exit_status"]).is_equal_to("0")

    def describe_environment() -> None:
        async def it_inherits_env_vars_from_parent_process(
            execute_command: ExecuteCommand, monkeypatch: pytest.MonkeyPatch
        ) -> None:
            monkeypatch.setenv("EXECUTE_CMD_TEST_VAR", "from_parent")
            result = await execute_command("printenv", ["EXECUTE_CMD_TEST_VAR"])
            assert_that(result.json()).is_equal_to({"exit_status": "0", "stdout": "from_parent\n", "stderr": ""})

        async def it_merges_additional_env_vars(execute_command: ExecuteCommand) -> None:
            result = await execute_command(
                "printenv", ["EXECUTE_CMD_EXTRA_VAR"], environment={"EXECUTE_CMD_EXTRA_VAR": "injected"}
            )
            assert_that(result.json()).is_equal_to({"exit_status": "0", "stdout": "injected\n", "stderr": ""})

        async def it_overrides_existing_env_vars(
            execute_command: ExecuteCommand, monkeypatch: pytest.MonkeyPatch
        ) -> None:
            monkeypatch.setenv("EXECUTE_CMD_TEST_VAR", "original")
            result = await execute_command(
                "printenv", ["EXECUTE_CMD_TEST_VAR"], environment={"EXECUTE_CMD_TEST_VAR": "overridden"}
            )
            assert_that(result.json()).is_equal_to({"exit_status": "0", "stdout": "overridden\n", "stderr": ""})

        async def it_passes_custom_path_to_child_process(execute_command: ExecuteCommand) -> None:
            # custom PATH is visible to the executed command (and its children)
            result = await execute_command("printenv", ["PATH"], environment={"PATH": "/custom/bin"})
            assert_that(result.json()).is_equal_to({"exit_status": "0", "stdout": "/custom/bin\n", "stderr": ""})

    def describe_summary() -> None:
        async def it_includes_summary_in_elicitation(execute_command: ExecuteCommand) -> None:
            result = await execute_command("ls", ["/tmp"], summary="listing tmp directory")
            assert_that(result.is_error).is_false()
            assert_that(result.json()["exit_status"]).is_equal_to("0")

    def describe_decline() -> None:
        async def it_returns_cancelled_when_user_declines(
            client_any_command: Client[FastMCPTransport], elicitor: Elicitor
        ) -> None:
            elicitor.decline(expect_message=assert_command_prompt("ls", ["/tmp"]))
            result = await client_any_command.call_tool(
                "execute_command", {"command": "ls", "arguments": ["/tmp"]}, raise_on_error=False
            )
            assert_that(result.is_error).is_true()
            assert isinstance(result.content[0], TextContent)
            assert_that(result.content[0].text).is_equal_to("Tool use was cancelled by the user")
