"""MCP list results must not require a hardcoded desktop session ID."""
import asyncio
import json
from types import SimpleNamespace

import pytest

from scripts.verify_release_agent import Acceptance


@pytest.mark.parametrize('sessions,structured,as_array', [
    ([], True, False),
    ([{'id': 'actual-window'}], False, False),
    ([{'id': 'one'}, {'id': 'two'}], False, False),
    ([{'id': 'actual-window'}], False, True),
    ([{'id': 'actual-window'}], True, False),
])
def test_real_session_list_transport_shapes(tmp_path, sessions, structured, as_array):
    async def call_tool(*args):
        values = [sessions] if as_array else sessions
        return SimpleNamespace(isError=False,
            content=[SimpleNamespace(text=json.dumps(value)) for value in values],
            structuredContent={'result': sessions} if structured else None)
    run = Acceptance.__new__(Acceptance)
    run.evidence = tmp_path
    assert asyncio.run(run.call(SimpleNamespace(call_tool=call_tool), 'operon_sessions')) == sessions
