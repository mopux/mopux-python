from __future__ import annotations

from collections.abc import Iterator

import pytest

import mopux._async.connector as async_connector
import mopux._sync.connector as sync_connector


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[float]]:
    """Records retry delays instead of sleeping."""
    delays: list[float] = []

    async def async_sleep(seconds: float) -> None:
        delays.append(seconds)

    monkeypatch.setattr(sync_connector.time, "sleep", delays.append)
    monkeypatch.setattr(async_connector.asyncio, "sleep", async_sleep)
    yield delays
