"""Tests for LuxDisplay — injected client provider/reset, no real lux."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any

import pytest

from punt_zspec.commands.show import DisplayError
from punt_zspec.display import LuxDisplay

_Call = tuple[str, tuple[object, ...], str, str]


def _recording_client(calls: list[_Call]) -> Any:
    class _C:
        def show(
            self,
            window_id: str,
            elements: list[object],
            *,
            frame_id: str,
            frame_title: str,
        ) -> None:
            calls.append((window_id, tuple(elements), frame_id, frame_title))

    return _C()


def _raising_client(exc: Exception) -> Any:
    class _C:
        def show(
            self,
            window_id: str,
            elements: list[object],
            *,
            frame_id: str,
            frame_title: str,
        ) -> None:
            raise exc

    return _C()


def _sequence_provider(clients: list[Any]) -> Callable[[], Any]:
    it: Iterator[Any] = iter(clients)

    def provide() -> Any:
        return next(it)

    return provide


def test_show_renders_on_first_client() -> None:
    calls: list[_Call] = []
    resets: list[int] = []
    scene = object()
    display = LuxDisplay(
        provide=_sequence_provider([_recording_client(calls)]),
        reset=lambda: resets.append(1),
    )

    display.show(scene, frame_id="z-spec", frame_title="Z-Spec: s.tex")

    assert calls == [("z-spec", (scene,), "z-spec", "Z-Spec: s.tex")]
    assert resets == []  # first render succeeded — no reconnect


def test_show_reconnects_once_then_succeeds() -> None:
    calls: list[_Call] = []
    resets: list[int] = []
    scene = object()
    display = LuxDisplay(
        provide=_sequence_provider(
            [_raising_client(ConnectionError("dropped")), _recording_client(calls)]
        ),
        reset=lambda: resets.append(1),
    )

    display.show(scene, frame_id="z-spec", frame_title="t")

    assert resets == [1]  # dropped the dead client before retrying
    assert calls == [("z-spec", (scene,), "z-spec", "t")]


def test_show_raises_display_error_after_second_failure() -> None:
    display = LuxDisplay(
        provide=_sequence_provider(
            [
                _raising_client(ConnectionError("first")),
                _raising_client(OSError("second")),
            ]
        ),
        reset=lambda: None,
    )

    with pytest.raises(DisplayError, match="second"):
        display.show(object(), frame_id="z-spec", frame_title="t")
