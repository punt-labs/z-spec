"""Tests for ZSpecLuxSession — the lifespan starts/stops cleanly, down luxd or not."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from punt_lux import HubUnavailableError

from punt_zspec.lux.clients import ZSpecLuxClients
from punt_zspec.lux.identity import ZSpecLuxIdentity
from punt_zspec.lux.session import ZSpecLuxSession

if TYPE_CHECKING:
    from pathlib import Path

    from pytest import MonkeyPatch

_FOR_IDENTITY = "punt_zspec.lux.clients.LuxRestClient.for_identity"


def _session(tmp_path: Path) -> ZSpecLuxSession:
    return ZSpecLuxSession(
        clients=ZSpecLuxClients(identity=ZSpecLuxIdentity("repo", 7)),
        cwd=tmp_path,
        tutorial_manifest=tmp_path / "manifest.toml",
    )


def test_start_then_stop_is_clean_when_luxd_is_down(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    def down(*_a: object, **_k: object) -> object:
        raise HubUnavailableError("luxd not running")

    monkeypatch.setattr(_FOR_IDENTITY, down)

    async def scenario() -> object:
        session = _session(tmp_path)
        # A down luxd at startup must be non-fatal: the listener retries and the
        # tool surface keeps working, so start() never raises.
        await session.start()
        await asyncio.sleep(0.05)  # let the listener attempt, fail, and back off
        await session.stop()  # cancel + drain must be clean
        return session.display

    display = asyncio.run(scenario())

    assert type(display).__name__ == "LuxDisplay"


def test_stop_before_start_is_safe(tmp_path: Path) -> None:
    async def scenario() -> None:
        session = _session(tmp_path)
        await session.stop()  # no task spawned yet — must not raise

    asyncio.run(scenario())
