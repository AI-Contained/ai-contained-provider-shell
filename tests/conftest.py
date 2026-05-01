from collections.abc import AsyncGenerator, Generator

import pytest
from fastmcp import FastMCP
from fastmcp.client import Client

from ai_contained.core.mcp.testing import Elicitor
from ai_contained.provider.shell import register


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
