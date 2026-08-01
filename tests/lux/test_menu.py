"""Tests for ZSpecMenuRegistrar — register_callback is best-effort, never fatal."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from punt_lux import HubUnavailableError
from punt_lux.operations import Ok, OpError

from punt_zspec.lux.menu import ZSpecMenuRegistrar

if TYPE_CHECKING:
    from punt_zspec.lux.ports import MenuClient


class _RecordingClient:
    """A MenuClient recording each register_callback and returning a set result."""

    def __init__(self, result: Ok | OpError) -> None:
        self._result = result
        self.calls: list[tuple[str, str]] = []

    def register_callback(self, callback_id: str, label: str) -> Ok | OpError:
        self.calls.append((callback_id, label))
        return self._result


def test_register_calls_register_callback_with_the_id_and_label() -> None:
    client = _RecordingClient(Ok())

    asyncio.run(ZSpecMenuRegistrar(lambda: client).register("z-spec-tutorial", "Label"))

    assert client.calls == [("z-spec-tutorial", "Label")]


def test_register_swallows_a_rejection() -> None:
    client = _RecordingClient(OpError(code="rejected", reason="bad label"))

    # A refused registration is logged, not raised — the receive leg survives.
    asyncio.run(ZSpecMenuRegistrar(lambda: client).register("id", "Label"))

    assert client.calls == [("id", "Label")]


def test_register_swallows_a_down_luxd() -> None:
    def connect() -> MenuClient:
        raise HubUnavailableError("luxd down")

    # Must return cleanly — a missing menu never crashes the daemon.
    asyncio.run(ZSpecMenuRegistrar(connect).register("id", "Label"))


def test_register_swallows_a_raising_client() -> None:
    class _Boom:
        def register_callback(self, callback_id: str, label: str) -> Ok | OpError:
            raise RuntimeError("transport blew up")

    asyncio.run(ZSpecMenuRegistrar(lambda: _Boom()).register("id", "Label"))
