import os
from collections.abc import AsyncGenerator, Generator
from pathlib import Path

import pytest
from assertpy import assert_that  # type: ignore[import-untyped]
from fastmcp import FastMCP
from fastmcp.client import Client
from fastmcp.client.transports import FastMCPTransport
from mcp.types import TextContent

from ai_contained.core.mcp.testing import Elicitor, WrapCallToolResult
from ai_contained.provider.shell.execute_command import _BLOCKED
from ai_contained.provider.shell.execute_command import register as register_execute_command


class ExecuteCommand:
    def __init__(self, client: Client[FastMCPTransport], elicitor: Elicitor) -> None:
        self.client = client
        self._elicitor = elicitor

    async def __call__(
        self,
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
        self._elicitor.accept(
            expect_message=assert_command_prompt(command, arguments, working_dir=working_dir, summary=summary)
        )
        return WrapCallToolResult(
            **vars(await self.client.call_tool(
                "execute_command",
                {"command": command, "arguments": arguments, "working_dir": working_dir, "environment": environment, "summary": summary},
                raise_on_error=raise_on_error,
            ))
        )


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
    async def execute_command(elicitor: Elicitor) -> AsyncGenerator[ExecuteCommand, None]:
        """Permissive client — no blocklist. Exposes .client for raw call_tool access."""
        server = FastMCP("test")
        register_execute_command(server, blocklist=frozenset())
        async with Client(transport=server, elicitation_handler=elicitor) as c:
            yield ExecuteCommand(c, elicitor)

    def describe_basic_execution() -> None:
        async def it_runs_a_command_and_returns_stdout(execute_command: ExecuteCommand, tmp_path: Path) -> None:
            expected = "world\n"
            hello_file = tmp_path / "hello.txt"
            hello_file.write_text(expected)
            result = await execute_command("cat", [str(hello_file)])
            assert_that(result.is_error).is_false()
            assert_that(result.json()).is_equal_to({"exit_status": "0", "stdout": expected, "stderr": ""})

        async def it_captures_stderr_and_nonzero_exit(execute_command: ExecuteCommand) -> None:
            expected = "/nonexistent_xyz_abc_123"
            result = await execute_command("cat", [expected])
            assert_that(result.is_error).is_false()
            assert_that(result.json()["exit_status"]).is_not_equal_to("0")
            assert_that(result.json()["stderr"]).contains(expected)

        async def it_captures_both_stdout_and_stderr(execute_command: ExecuteCommand, tmp_path: Path) -> None:
            expected_stdout = "world\n"
            expected_missing = "/nonexistent_xyz_abc_123"
            hello_file = tmp_path / "hello.txt"
            hello_file.write_text(expected_stdout)
            result = await execute_command("cat", [str(hello_file), expected_missing])
            assert_that(result.is_error).is_false()
            assert_that(result.json()["stdout"]).is_equal_to(expected_stdout)
            assert_that(result.json()["stderr"]).contains(expected_missing)

    def describe_arguments() -> None:
        async def it_does_not_expand_env_vars_in_arguments(
            execute_command: ExecuteCommand, monkeypatch: pytest.MonkeyPatch
        ) -> None:
            expected = "$EXECUTE_CMD_TEST_VAR"
            monkeypatch.setenv("EXECUTE_CMD_TEST_VAR", "should_not_appear")
            result = await execute_command("echo", [expected])
            assert_that(result.json()).is_equal_to({"exit_status": "0", "stdout": f"{expected}\n", "stderr": ""})

        async def it_does_not_expand_shell_globs(execute_command: ExecuteCommand, tmp_path: Path) -> None:
            expected = str(tmp_path / "*.txt")
            result = await execute_command("ls", [expected])
            assert_that(result.json()["exit_status"]).is_not_equal_to("0")
            assert_that(result.json()["stderr"]).contains(expected)

    def describe_blocklist() -> None:
        @pytest.mark.parametrize("expected", sorted(_BLOCKED))
        async def it_rejects_blocked_commands(
            client: Client[FastMCPTransport], expected: str
        ) -> None:
            result = await client.call_tool(
                "execute_command", {"command": expected, "arguments": []}, raise_on_error=False
            )
            assert_that(result.is_error).is_true()
            assert isinstance(result.content[0], TextContent)
            assert_that(result.content[0].text).is_equal_to(f"execute_command: {expected!r} is not permitted")

        async def it_rejects_absolute_path_to_blocked_command(
            client: Client[FastMCPTransport],
        ) -> None:
            expected = "bash"
            result = await client.call_tool(
                "execute_command", {"command": f"/bin/{expected}", "arguments": []}, raise_on_error=False
            )
            assert_that(result.is_error).is_true()
            assert isinstance(result.content[0], TextContent)
            assert_that(result.content[0].text).is_equal_to(f"execute_command: {expected!r} is not permitted")

        async def it_rejects_before_elicitation(
            client: Client[FastMCPTransport], elicitor: Elicitor
        ) -> None:
            result = await client.call_tool(
                "execute_command", {"command": "bash", "arguments": []}, raise_on_error=False
            )
            assert_that(result.is_error).is_true()

    def describe_path_resolution() -> None:
        async def it_accepts_absolute_path(execute_command: ExecuteCommand, tmp_path: Path) -> None:
            expected = "world\n"
            hello_file = tmp_path / "hello.txt"
            hello_file.write_text(expected)
            result = await execute_command("/bin/cat", [str(hello_file)])
            assert_that(result.json()).is_equal_to({"exit_status": "0", "stdout": expected, "stderr": ""})

        async def it_rejects_unknown_command(execute_command: ExecuteCommand) -> None:
            expected = "nonexistent_command_xyz_abc"
            result = await execute_command.client.call_tool(
                "execute_command", {"command": expected, "arguments": []}, raise_on_error=False
            )
            assert_that(result.is_error).is_true()
            assert isinstance(result.content[0], TextContent)
            assert_that(result.content[0].text).is_equal_to(f"execute_command: {expected!r} not found in PATH")

    def describe_working_dir() -> None:
        @pytest.fixture
        def sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[Path, None, None]:
            root = tmp_path / "root"
            root.mkdir()
            monkeypatch.chdir(root)
            yield root

        async def it_runs_in_specified_working_dir(execute_command: ExecuteCommand, sandbox: Path) -> None:
            expected = sandbox / "work"
            expected.mkdir()
            result = await execute_command("pwd", working_dir=str(expected))
            assert_that(result.json()).is_equal_to({"exit_status": "0", "stdout": f"{expected}\n", "stderr": ""})

        async def it_shows_relative_path_in_elicitation(execute_command: ExecuteCommand, sandbox: Path) -> None:
            result = await execute_command("pwd", working_dir="/tmp")
            assert_that(result.json()["exit_status"]).is_equal_to("0")

    def describe_environment() -> None:
        async def it_inherits_env_vars_from_parent_process(
            execute_command: ExecuteCommand, monkeypatch: pytest.MonkeyPatch
        ) -> None:
            expected = "from_parent"
            monkeypatch.setenv("EXECUTE_CMD_TEST_VAR", expected)
            result = await execute_command("printenv", ["EXECUTE_CMD_TEST_VAR"])
            assert_that(result.json()).is_equal_to({"exit_status": "0", "stdout": f"{expected}\n", "stderr": ""})

        async def it_merges_additional_env_vars(execute_command: ExecuteCommand) -> None:
            expected = "injected"
            result = await execute_command(
                "printenv", ["EXECUTE_CMD_EXTRA_VAR"], environment={"EXECUTE_CMD_EXTRA_VAR": expected}
            )
            assert_that(result.json()).is_equal_to({"exit_status": "0", "stdout": f"{expected}\n", "stderr": ""})

        async def it_overrides_existing_env_vars(
            execute_command: ExecuteCommand, monkeypatch: pytest.MonkeyPatch
        ) -> None:
            expected = "overridden"
            monkeypatch.setenv("EXECUTE_CMD_TEST_VAR", "original")
            result = await execute_command(
                "printenv", ["EXECUTE_CMD_TEST_VAR"], environment={"EXECUTE_CMD_TEST_VAR": expected}
            )
            assert_that(result.json()).is_equal_to({"exit_status": "0", "stdout": f"{expected}\n", "stderr": ""})

        async def it_expands_variables_in_environment_values(
            execute_command: ExecuteCommand, monkeypatch: pytest.MonkeyPatch
        ) -> None:
            base = "whatever"
            expected = f"-{base}-"
            monkeypatch.setenv("EXECUTE_CMD_BASE_VAR", base)
            result = await execute_command(
                "printenv", ["EXECUTE_CMD_DERIVED_VAR"],
                environment={"EXECUTE_CMD_DERIVED_VAR": "-$EXECUTE_CMD_BASE_VAR-"},
            )
            assert_that(result.json()).is_equal_to({"exit_status": "0", "stdout": f"{expected}\n", "stderr": ""})

        async def it_resolves_command_via_environment_path(
            execute_command: ExecuteCommand,
        ) -> None:
            expected = Path(__file__).parent / "bin" / "test_helper"
            result = await execute_command("which", ["test_helper"], environment={"PATH": f"{expected.parent}:$PATH"})
            assert_that(result.json()).is_equal_to({"exit_status": "0", "stdout": f"{expected}\n", "stderr": ""})

        async def it_executes_command_found_via_environment_path(
            execute_command: ExecuteCommand,
        ) -> None:
            expected = "test_helper"
            bin_dir = Path(__file__).parent / "bin"
            result = await execute_command("test_helper", [], environment={"PATH": str(bin_dir)})
            assert_that(result.json()).is_equal_to({"exit_status": "0", "stdout": f"{expected}\n", "stderr": ""})

    def describe_summary() -> None:
        async def it_includes_summary_in_elicitation(execute_command: ExecuteCommand) -> None:
            expected = "listing tmp directory"
            result = await execute_command("ls", ["/tmp"], summary=expected)
            assert_that(result.is_error).is_false()
            assert_that(result.json()["exit_status"]).is_equal_to("0")

    def describe_decline() -> None:
        async def it_returns_cancelled_when_user_declines(
            execute_command: ExecuteCommand, elicitor: Elicitor
        ) -> None:
            expected = "Tool use was cancelled by the user"
            elicitor.decline(expect_message=assert_command_prompt("ls", ["/tmp"]))
            result = await execute_command.client.call_tool(
                "execute_command", {"command": "ls", "arguments": ["/tmp"]}, raise_on_error=False
            )
            assert_that(result.is_error).is_true()
            assert isinstance(result.content[0], TextContent)
            assert_that(result.content[0].text).is_equal_to(expected)
