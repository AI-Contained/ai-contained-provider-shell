import json
from collections.abc import AsyncGenerator, Generator
from dataclasses import dataclass
from typing import Any, Callable, Literal, Self

import pytest
from assertpy import assert_that
from fastmcp import FastMCP
from fastmcp.client import Client
from fastmcp.client.client import CallToolResult
from fastmcp.client.elicitation import ElicitRequestParams, ElicitResult
from mcp import ClientSession
from mcp.shared.context import RequestContext

from ai_contained.provider.shell import register


@dataclass
class WrapCallToolResult(CallToolResult):
    def json(self) -> Any:
        return json.loads(self.content[0].text)

ElicitAction = Literal["accept", "decline", "cancel"]
ElicitContent = dict[str, Any] | str | int | float | bool | None
ElicitResponse = tuple[ElicitAction, ElicitContent]
ElicitCallback = Callable[
    [str, type | None, ElicitRequestParams, RequestContext[ClientSession, Any]],
    ElicitResponse,
]


class Elicitor:
    def __init__(self) -> None:
        self._queue: list[ElicitCallback] = []

    def on_elicit(self, fn: ElicitCallback) -> Self:
        self._queue.append(fn)
        return self

    def accept(self, value: ElicitContent = None, *, expect_message: str | None = None) -> Self:
        def step(msg: str, rtype: type | None, params: ElicitRequestParams, ctx: RequestContext[ClientSession, Any]) -> ElicitResponse:
            if expect_message is not None:
                assert_that(msg).is_equal_to(expect_message)
            return ("accept", value)
        return self.on_elicit(step)

    def decline(self, *, expect_message: str | None = None) -> Self:
        def step(msg: str, rtype: type | None, params: ElicitRequestParams, ctx: RequestContext[ClientSession, Any]) -> ElicitResponse:
            if expect_message is not None:
                assert_that(msg).is_equal_to(expect_message)
            return ("decline", None)
        return self.on_elicit(step)

    def cancel(self, *, expect_message: str | None = None) -> Self:
        def step(msg: str, rtype: type | None, params: ElicitRequestParams, ctx: RequestContext[ClientSession, Any]) -> ElicitResponse:
            if expect_message is not None:
                assert_that(msg).is_equal_to(expect_message)
            return ("cancel", None)
        return self.on_elicit(step)

    async def __call__(self, message: str, response_type: type | None, params: ElicitRequestParams, context: RequestContext[ClientSession, Any]) -> ElicitResult:
        assert self._queue, f"Unexpected elicitation: {message!r}"
        action, content = self._queue.pop(0)(message, response_type, params, context)
        return ElicitResult(action=action, content=content)


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
