"""Humble-object tests for ZSpecSubscription — routing, loop-safety, register.

No live Hub: fake command factories, a fake registrar, and a fake Display drive
the receive leg. Async tests run on a throwaway loop via ``asyncio.run``.
"""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from typing import TYPE_CHECKING

from punt_zspec.commands.show import DisplayError
from punt_zspec.lux.subscription import ZSpecMenuEntry, ZSpecSubscription

if TYPE_CHECKING:
    from punt_lux import CallbackHandler, EventHandler
    from punt_lux.hub_client import ConnectHandler

    from punt_zspec.commands.show import Display
    from punt_zspec.lux.command_ports import ClickCommand, ClickCommandFactory
    from punt_zspec.lux.ports import HubListener

_MANIFEST = Path("tutorials/intro/manifest.toml")
_CWD = Path("/work/repo")


class _RecordingCommand:
    """A ClickCommand that records the (target, frame_id) it was run with."""

    def __init__(self, log: list[tuple[Path, str]]) -> None:
        self._log = log

    def run(self, target: Path, /, *, frame_id: str) -> object:
        self._log.append((target, frame_id))
        return object()


def _recording_factory(log: list[tuple[Path, str]]) -> ClickCommandFactory:
    def make(_display: Display) -> ClickCommand:
        return _RecordingCommand(log)

    return make


class _RecordingDisplay:
    """A Display that records each (frame_id, frame_title) show."""

    def __init__(self) -> None:
        self.shows: list[tuple[str, str]] = []

    def show(self, scene: object, *, frame_id: str, frame_title: str) -> None:
        self.shows.append((frame_id, frame_title))


class _FailingDisplay:
    """A Display whose show always raises — luxd unreachable."""

    def show(self, scene: object, *, frame_id: str, frame_title: str) -> None:
        raise DisplayError("lux down")


class _RecordingMenu:
    """A MenuRegistrar that records each (callback_id, label) registration."""

    def __init__(self) -> None:
        self.registered: list[tuple[str, str]] = []

    async def register(self, callback_id: str, label: str) -> None:
        self.registered.append((callback_id, label))


def _unused_listen(
    *,
    on_callback: CallbackHandler,
    on_event: EventHandler,
    on_connect: ConnectHandler,
) -> HubListener:
    raise AssertionError("the listener factory must not be called in these tests")


def _entries(
    tutorial_log: list[tuple[Path, str]], browse_log: list[tuple[Path, str]]
) -> tuple[ZSpecMenuEntry, ...]:
    return (
        ZSpecMenuEntry(
            callback_id="z-spec-tutorial",
            label="z-spec Tutorial · repo · #1",
            scene_id="z-spec-tutorial",
            scene_title="Z-Spec Tutorial",
            factory=_recording_factory(tutorial_log),
            target=_MANIFEST,
        ),
        ZSpecMenuEntry(
            callback_id="z-spec-browse",
            label="z-spec Browse · repo · #1",
            scene_id="z-spec-picker",
            scene_title="Z Specs",
            factory=_recording_factory(browse_log),
            target=_CWD,
        ),
    )


def _subscription(
    display: Display,
    menu: _RecordingMenu | None = None,
    tutorial_log: list[tuple[Path, str]] | None = None,
    browse_log: list[tuple[Path, str]] | None = None,
) -> ZSpecSubscription:
    return ZSpecSubscription(
        entries=_entries(
            tutorial_log if tutorial_log is not None else [],
            browse_log if browse_log is not None else [],
        ),
        menu=menu if menu is not None else _RecordingMenu(),
        listen=_unused_listen,
        display=display,
    )


def test_tutorial_click_runs_the_tutorial_command_with_matching_scene_id() -> None:
    async def scenario() -> tuple[list[tuple[Path, str]], list[tuple[str, str]]]:
        tut: list[tuple[Path, str]] = []
        display = _RecordingDisplay()
        sub = _subscription(display, tutorial_log=tut)
        await sub.on_callback("z-spec-tutorial")
        return tut, display.shows

    tut, shows = asyncio.run(scenario())

    # The command renders into the SAME id the placeholder raised (ADR §5.2).
    assert tut == [(_MANIFEST, "z-spec-tutorial")]
    assert shows == [("z-spec-tutorial", "Z-Spec Tutorial")]


def test_browse_click_runs_the_picker_command_on_the_cwd() -> None:
    async def scenario() -> tuple[list[tuple[Path, str]], list[tuple[str, str]]]:
        brw: list[tuple[Path, str]] = []
        display = _RecordingDisplay()
        sub = _subscription(display, browse_log=brw)
        await sub.on_callback("z-spec-browse")
        return brw, display.shows

    brw, shows = asyncio.run(scenario())

    assert brw == [(_CWD, "z-spec-picker")]
    assert shows == [("z-spec-picker", "Z Specs")]


def test_unknown_callback_is_a_noop() -> None:
    async def scenario() -> tuple[list[tuple[Path, str]], list[tuple[Path, str]], int]:
        tut: list[tuple[Path, str]] = []
        brw: list[tuple[Path, str]] = []
        display = _RecordingDisplay()
        sub = _subscription(display, tutorial_log=tut, browse_log=brw)
        await sub.on_callback("nope")
        return tut, brw, len(display.shows)

    tut, brw, shown = asyncio.run(scenario())

    assert (tut, brw, shown) == ([], [], 0)


def test_callback_does_not_block_the_event_loop() -> None:
    """Loop-starvation guard: the blocking render is off-loaded, not run inline."""

    async def scenario() -> bool:
        latch = threading.Event()
        entered = threading.Event()

        class _BlockingDisplay:
            def show(self, scene: object, *, frame_id: str, frame_title: str) -> None:
                entered.set()
                if not latch.wait(timeout=5):
                    raise AssertionError("latch never released")

        sub = _subscription(_BlockingDisplay())
        task = asyncio.create_task(sub.on_callback("z-spec-browse"))
        # If the render ran inline on the loop, this sleep could not complete
        # until the latch releases (the loop would be stuck in show). With
        # asyncio.to_thread the loop stays free, so control returns here while
        # show is still blocked in the worker thread.
        await asyncio.sleep(0.1)
        progressed = entered.is_set() and not task.done()
        latch.set()
        await asyncio.wait_for(task, timeout=2)
        return progressed

    assert asyncio.run(scenario()) is True


def test_on_connect_registers_both_entries_with_two_axis_labels() -> None:
    async def scenario() -> list[tuple[str, str]]:
        menu = _RecordingMenu()
        sub = _subscription(_RecordingDisplay(), menu=menu)
        await sub.on_connect()
        return menu.registered

    registered = asyncio.run(scenario())

    assert registered == [
        ("z-spec-tutorial", "z-spec Tutorial · repo · #1"),
        ("z-spec-browse", "z-spec Browse · repo · #1"),
    ]


def test_on_event_is_a_noop() -> None:
    async def scenario() -> None:
        sub = _subscription(_RecordingDisplay())
        # z-spec subscribes to no topics; a stray event must never raise.
        await sub.on_event("music.play", {"album": "x"})

    asyncio.run(scenario())


def test_a_down_display_does_not_crash_a_click() -> None:
    async def scenario() -> list[tuple[Path, str]]:
        brw: list[tuple[Path, str]] = []
        sub = _subscription(_FailingDisplay(), browse_log=brw)
        # The placeholder raise fails (DisplayError swallowed); the command still
        # runs — a down display is best-effort, never fatal.
        await sub.on_callback("z-spec-browse")
        return brw

    brw = asyncio.run(scenario())

    assert brw == [(_CWD, "z-spec-picker")]


def test_stop_is_safe_before_any_connection() -> None:
    sub = _subscription(_RecordingDisplay())

    sub.stop()  # no listener built yet — must not raise
