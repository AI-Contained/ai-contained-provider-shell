import os
from collections.abc import AsyncGenerator, Callable, Coroutine, Generator
from pathlib import Path
from typing import Any

import pytest
from assertpy import assert_that
from fastmcp import FastMCP
from fastmcp.client import Client

from ai_contained.core.mcp.testing import Elicitor, WrapCallToolResult
from ai_contained.provider.shell import register


def assert_bash_prompt(command: str, working_dir: str | None = None, summary: str | None = None) -> str:
    if working_dir:
        rel = os.path.relpath(working_dir)
        msg = f"I will run the following command: {command} (in {rel}) (using tool: shell)"
    else:
        msg = f"I will run the following command: {command} (using tool: shell)"
    if summary:
        msg += f"\nPurpose: {summary}"
    return msg


def describe_execute_bash():

    @pytest.fixture
    def elicitor() -> Generator[Elicitor, None, None]:
        e = Elicitor()
        yield e
        assert not e._queue, f"{len(e._queue)} elicitation step(s) were never triggered"

    @pytest.fixture
    async def client(elicitor: Elicitor) -> AsyncGenerator[Client, None]:
        server = FastMCP("test")
        register(server)
        async with Client(transport=server, elicitation_handler=elicitor) as c:
            yield c


    @pytest.fixture
    def execute_bash(client: Client, elicitor: Elicitor) -> Callable[..., Coroutine[Any, Any, Any]]:
        async def _run(command: str, *, working_dir: str | None = None, summary: str | None = None, raise_on_error: bool = True) -> WrapCallToolResult:
            elicitor.accept(expect_message=assert_bash_prompt(command, working_dir=working_dir, summary=summary))
            args: dict[str, str] = {"command": command}
            if working_dir:
                args["working_dir"] = working_dir
            if summary:
                args["summary"] = summary
            return WrapCallToolResult(**vars(await client.call_tool("execute_bash", args, raise_on_error=raise_on_error)))
        return _run

    def describe_basic_execution():
        async def it_runs_a_command_and_returns_stdout(execute_bash):
            result = await execute_bash('echo "hello"')
            assert_that(result.is_error).is_false()
            assert_that(result.json()).is_equal_to({"exit_status": "0", "stdout": "hello\n", "stderr": ""})

        async def it_captures_stderr(execute_bash):
            result = await execute_bash('echo "err" >&2')
            assert_that(result.is_error).is_false()
            assert_that(result.json()).is_equal_to({"exit_status": "0", "stdout": "", "stderr": "err\n"})

        async def it_captures_both_stdout_and_stderr(execute_bash):
            result = await execute_bash('echo "out" && echo "err" >&2')
            assert_that(result.is_error).is_false()
            assert_that(result.json()).is_equal_to({"exit_status": "0", "stdout": "out\n", "stderr": "err\n"})

        async def it_captures_stdout_stderr_and_nonzero_exit(execute_bash, tmp_path: Path):
            file_name = tmp_path / "sample.txt"
            file_content = "test data\n"
            file_name.write_text(file_content)
            result = await execute_bash(f'cat {file_name}; echo "error: not found" >&2; exit 2')
            assert_that(result.is_error).is_false()
            assert_that(result.json()).is_equal_to({
                "exit_status": "2",
                "stdout": file_content,
                "stderr": "error: not found\n",
            })

    def describe_exit_status():
        async def it_returns_nonzero_exit_status(execute_bash):
            result = await execute_bash("exit 1")
            assert_that(result.is_error).is_false()
            assert_that(result.json()).is_equal_to({"exit_status": "1", "stdout": "", "stderr": ""})

        async def it_returns_exit_status_as_string_not_int(execute_bash):
            result = await execute_bash("exit 0")
            assert_that(result.json()["exit_status"]).is_instance_of(str)

        async def it_returns_stderr_on_failed_command(execute_bash):
            result = await execute_bash('echo "error: not found" >&2; exit 2')
            assert_that(result.is_error).is_false()
            assert_that(result.json()).is_equal_to({"exit_status": "2", "stdout": "", "stderr": "error: not found\n"})

    def describe_working_dir():

        @pytest.fixture
        def sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[Path, None, None]:
            root = tmp_path / "root"
            root.mkdir()
            monkeypatch.chdir(root)
            yield root

        async def it_runs_in_specified_working_dir(execute_bash, sandbox):
            bash_dir = sandbox / "volatile" / "bash_test"
            bash_dir.mkdir(parents=True)
            result = await execute_bash("pwd", working_dir=str(bash_dir))
            assert_that(result.is_error).is_false()
            assert_that(result.json()).is_equal_to({"exit_status": "0", "stdout": f"{bash_dir}\n", "stderr": ""})

        async def it_shows_relative_path_for_dir_outside_cwd(execute_bash, sandbox):
            result = await execute_bash("pwd", working_dir="/tmp")
            assert_that(result.is_error).is_false()
            assert_that(result.json()).is_equal_to({"exit_status": "0", "stdout": "/tmp\n", "stderr": ""})

    def describe_environment():
        async def it_inherits_env_vars_from_parent_process(execute_bash, monkeypatch):
            monkeypatch.setenv("TEST_GREETING", "hello_from_env")
            result = await execute_bash("echo $TEST_GREETING")
            assert_that(result.json()).is_equal_to({"exit_status": "0", "stdout": "hello_from_env\n", "stderr": ""})

    def describe_summary():
        async def it_includes_summary_in_elicitation(execute_bash):
            result = await execute_bash('echo "hello"', summary="This is a summary")
            assert_that(result.is_error).is_false()
            assert_that(result.json()).is_equal_to({"exit_status": "0", "stdout": "hello\n", "stderr": ""})

    def describe_decline():
        async def it_returns_cancelled_when_user_declines(client, elicitor):
            elicitor.decline(expect_message=assert_bash_prompt('echo "hello"'))
            result = await client.call_tool("execute_bash", {"command": 'echo "hello"'}, raise_on_error=False)
            assert_that(result.is_error).is_true()
            assert_that(result.content[0].text).is_equal_to("Tool use was cancelled by the user")
