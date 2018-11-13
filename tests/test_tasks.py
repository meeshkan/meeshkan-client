import asyncio

import pytest

# from meeshkan.tasks import TaskPoller, TaskSource


@pytest.mark.asyncio
async def test_app():
    await asyncio.sleep(1)
    assert 1 == 0
