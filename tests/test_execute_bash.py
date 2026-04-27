import json
import os
import pytest
from assertpy import assert_that
from fastmcp.client import Client

from conftest import make_capture_handler, make_decline_handler


#@pytest.fixture()
#def sandbox(tmp_path, monkeypatch):
#    cwd = tmp_path / "root"
#    sb = cwd / "volatile" / "bash_test"
#    sb.mkdir(parents=True)
#    (tmp_path / "tmp").mkdir()
#    (sb / "sample.txt").write_text("hello\n")
#    monkeypatch.chdir(cwd)
#    # Inject a known env var so tests can verify shell inherits the parent process environment
#    monkeypatch.setenv("TEST_GREETING", "hello_from_env")
#    return sb


@pytest.fixture(autouse=True)
def expected(sandbox):
    # Inject a known env var so tests can verify shell inherits the parent process environment
    sb = sandbox / "volatile" / "bash_test"
    sb.mkdir(parents=True)
    file_name = sb / "sample.txt"
    file_content = "test data\n"
    file_name.write_text(file_content)
    os.environ["TEST_GREETING"] = "hello_from_env"
    return {"root": sb,
            "file_name": str(file_name),
            "file_content": file_content}


def result_data(result):
    return json.loads(result.content[0].text)


def describe_execute_bash():

    def describe_basic_execution():
        async def it_runs_a_command_and_returns_stdout(mcp, expected):
            h = make_capture_handler()
            async with Client(transport=mcp, elicitation_handler=h) as client:
                result = await client.call_tool("execute_bash", {"command": 'echo "hello"'})
                assert_that(result.is_error).is_false()
                assert_that(h.messages[0]).is_equal_to('I will run the following command: echo "hello" (using tool: shell)')
                assert_that(result_data(result)).is_equal_to({"exit_status": "0", "stdout": "hello\n", "stderr": ""})

        async def it_captures_stderr(mcp, expected):
            h = make_capture_handler()
            async with Client(transport=mcp, elicitation_handler=h) as client:
                result = await client.call_tool("execute_bash", {"command": 'echo "err" >&2'})
                assert_that(result.is_error).is_false()
                assert_that(h.messages[0]).is_equal_to('I will run the following command: echo "err" >&2 (using tool: shell)')
                assert_that(result_data(result)).is_equal_to({"exit_status": "0", "stdout": "", "stderr": "err\n"})

        async def it_captures_both_stdout_and_stderr(mcp, expected):
            h = make_capture_handler()
            async with Client(transport=mcp, elicitation_handler=h) as client:
                result = await client.call_tool("execute_bash", {"command": 'echo "out" && echo "err" >&2'})
                assert_that(result.is_error).is_false()
                assert_that(h.messages[0]).is_equal_to('I will run the following command: echo "out" && echo "err" >&2 (using tool: shell)')
                assert_that(result_data(result)).is_equal_to({"exit_status": "0", "stdout": "out\n", "stderr": "err\n"})

        async def it_captures_stdout_and_stderr_with_nonzero_exit(mcp, expected):
            h = make_capture_handler()
            async with Client(transport=mcp, elicitation_handler=h) as client:
                command = f'cat {expected["file_name"]}; echo "error: not found" >&2; exit 2'
                result = await client.call_tool("execute_bash", {"command": command})
                assert_that(result.is_error).is_false()
                assert_that(h.messages[0]).is_equal_to(f"I will run the following command: {command} (using tool: shell)")
                assert_that(result_data(result)).is_equal_to({
                    "exit_status": "2",
                    "stdout": expected["file_content"],
                    "stderr": "error: not found\n",
                })

    def describe_exit_status():
        async def it_returns_nonzero_exit_status(mcp, expected):
            h = make_capture_handler()
            async with Client(transport=mcp, elicitation_handler=h) as client:
                result = await client.call_tool("execute_bash", {"command": "exit 1"})
                assert_that(result.is_error).is_false()
                assert_that(h.messages[0]).is_equal_to("I will run the following command: exit 1 (using tool: shell)")
                assert_that(result_data(result)).is_equal_to({"exit_status": "1", "stdout": "", "stderr": ""})

        async def it_returns_exit_status_as_string_not_int(mcp, expected):
            h = make_capture_handler()
            async with Client(transport=mcp, elicitation_handler=h) as client:
                result = await client.call_tool("execute_bash", {"command": "exit 0"})
                assert_that(result.is_error).is_false()
                assert_that(result_data(result)["exit_status"]).is_instance_of(str)

        async def it_returns_stderr_on_failed_command(mcp, expected):
            h = make_capture_handler()
            async with Client(transport=mcp, elicitation_handler=h) as client:
                command = 'echo "error: not found" >&2; exit 2'
                result = await client.call_tool("execute_bash", {"command": command})
                assert_that(result.is_error).is_false()
                assert_that(h.messages[0]).is_equal_to(f"I will run the following command: {command} (using tool: shell)")
                assert_that(result_data(result)).is_equal_to({
                    "exit_status": "2",
                    "stdout": "",
                    "stderr": "error: not found\n",
                })

    def describe_working_dir():
        async def it_runs_in_specified_working_dir(mcp, expected):
            h = make_capture_handler()
            async with Client(transport=mcp, elicitation_handler=h) as client:
                result = await client.call_tool("execute_bash", {"command": "pwd", "working_dir": expected["root"]})
                assert_that(result.is_error).is_false()
                assert_that(h.messages[0]).is_equal_to("I will run the following command: pwd (in volatile/bash_test) (using tool: shell)")
                assert_that(result_data(result)).is_equal_to({"exit_status": "0", "stdout": f"{expected["root"]}\n", "stderr": ""})

        async def it_shows_relative_path_for_dir_outside_cwd(mcp, expected):
            h = make_capture_handler()
            async with Client(transport=mcp, elicitation_handler=h) as client:
                result = await client.call_tool("execute_bash", {"command": "pwd", "working_dir": "/tmp"})
                assert_that(result.is_error).is_false()
                rel = os.path.relpath("/tmp")
                assert_that(h.messages[0]).is_equal_to(f"I will run the following command: pwd (in {rel}) (using tool: shell)")
                assert_that(result_data(result)).is_equal_to({"exit_status": "0", "stdout": "/tmp\n", "stderr": ""})

    def describe_environment():
        async def it_inherits_env_vars_from_parent_process(mcp, expected):
            h = make_capture_handler()
            async with Client(transport=mcp, elicitation_handler=h) as client:
                result = await client.call_tool("execute_bash", {"command": "echo $TEST_GREETING"})
                assert_that(result.is_error).is_false()
                assert_that(result_data(result)).is_equal_to({"exit_status": "0", "stdout": "hello_from_env\n", "stderr": ""})

    def describe_summary():
        async def it_includes_summary_in_elicitation(mcp, expected):
            h = make_capture_handler()
            async with Client(transport=mcp, elicitation_handler=h) as client:
                result = await client.call_tool("execute_bash", {"command": 'echo "hello"', "summary": "This is a summary"})
                assert_that(result.is_error).is_false()
                assert_that(h.messages[0]).is_equal_to('I will run the following command: echo "hello" (using tool: shell)\nPurpose: This is a summary')
                assert_that(result_data(result)).is_equal_to({"exit_status": "0", "stdout": "hello\n", "stderr": ""})

    def describe_decline():
        async def it_returns_cancelled_when_user_declines(mcp, expected):
            h = make_decline_handler()
            async with Client(transport=mcp, elicitation_handler=h) as client:
                result = await client.call_tool("execute_bash", {"command": 'echo "hello"'}, raise_on_error=False)
                assert_that(result.is_error).is_true()
                assert_that(h.messages[0]).is_equal_to('I will run the following command: echo "hello" (using tool: shell)')
                assert_that(result.content[0].text).is_equal_to("Tool use was cancelled by the user")
