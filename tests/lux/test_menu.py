"""Tests for ZSpecMenuRegistrar — register_callback is best-effort, never fatal."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from punt_lux import HubUnavailableError
from punt_lux.operations import Ok, OpError

import punt_zspec.lux.menu as menu
from punt_zspec.lux.menu import ZSpecMenuRegistrar

if TYPE_CHECKING:
    from pytest import MonkeyPatch

    from punt_zspec.lux.ports import MenuClient

_TEST_CAP = 3


class _RecordingClient:
    """A MenuClient recording each register_callback and returning a set result."""

    def __init__(self, result: Ok | OpError) -> None:
        self._result = result
        self.calls: list[tuple[str, str]] = []

    def register_callback(self, callback_id: str, label: str) -> Ok | OpError:
        self.calls.append((callback_id, label))
        return self._result


class _FlakyClient:
    """A MenuClient that returns OpError for the first ``fail_times`` calls, then Ok."""

    def __init__(self, fail_times: int) -> None:
        self._fail_times = fail_times
        self.calls: list[tuple[str, str]] = []

    def register_callback(self, callback_id: str, label: str) -> Ok | OpError:
        self.calls.append((callback_id, label))
        if len(self.calls) <= self._fail_times:
            return OpError(code="rejected", reason="no listen leg")
        return Ok()


def test_register_calls_register_callback_with_the_id_and_label() -> None:
    client = _RecordingClient(Ok())

    asyncio.run(ZSpecMenuRegistrar(lambda: client).register("z-spec-tutorial", "Label"))

    # The happy path succeeds on the FIRST attempt — the retry never fires.
    assert client.calls == [("z-spec-tutorial", "Label")]


def test_register_retries_a_transient_rejection_then_succeeds(
    monkeypatch: MonkeyPatch,
) -> None:
    # Collapse the backoff so the retry runs instantly (setattr by string name keeps
    # the module constant private to production code).
    monkeypatch.setattr(menu, "_RETRY_BACKOFF_SECONDS", 0.0)
    client = _FlakyClient(fail_times=2)

    asyncio.run(ZSpecMenuRegistrar(lambda: client).register("id", "Label"))

    # Two refusals, then Ok — three calls total, then it stops (idempotent by id).
    assert client.calls == [("id", "Label")] * 3


def test_register_gives_up_after_the_cap_without_raising(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(menu, "_RETRY_BACKOFF_SECONDS", 0.0)
    monkeypatch.setattr(menu, "_MAX_ATTEMPTS", _TEST_CAP)
    client = _RecordingClient(OpError(code="rejected", reason="no listen leg"))

    # Every attempt is refused: it retries to the cap, logs, and returns — never
    # raising, so the receive leg survives a persistent rejection.
    asyncio.run(ZSpecMenuRegistrar(lambda: client).register("id", "Label"))

    assert client.calls == [("id", "Label")] * _TEST_CAP


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
