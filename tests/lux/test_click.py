"""Tests for the click path: render the entry, report a failure into its frame.

No live Hub — a fake Display stands in for the render. luxd raises the clicked
entry's frame Display-locally (punt-lux DES-088), so the runner never raises a
frame itself. Async tests run on a throwaway loop via ``asyncio.run``.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from pathlib import Path
from typing import TYPE_CHECKING

from punt_zspec.commands.picker import PickerResult
from punt_zspec.commands.result import CommandError, CommandFailure, CommandResult
from punt_zspec.commands.show import DisplayError
from punt_zspec.lux.click import ZSpecClickRunner
from punt_zspec.lux.entry import ZSpecMenuEntry

if TYPE_CHECKING:
    import pytest

    from punt_zspec.commands.show import Display
    from punt_zspec.lux.command_ports import ClickCommand, ClickOutcome

_PROJECT = Path("/work/repo")
_OK: ClickOutcome = CommandResult.ok(PickerResult(total=1, scene_id="z-spec-picker"))
_FAILED: ClickOutcome = CommandResult[PickerResult].failed(
    CommandError(CommandFailure.spec_not_found, "No Z specs found in /work/repo")
)


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


def _entry(outcome: ClickOutcome = _OK, ran: list[str] | None = None) -> ZSpecMenuEntry:
    log = ran if ran is not None else []

    class _Command:
        def run(
            self, target: Path, /, *, frame_id: str, frame_title: str
        ) -> ClickOutcome:
            log.append(frame_id)
            return outcome

    def factory(_display: Display) -> ClickCommand:
        return _Command()

    return ZSpecMenuEntry(
        callback_id="z-spec-browse",
        title="Z-Spec Browser",
        scene_id="z-spec-picker",
        factory=factory,
        target=_PROJECT,
    )


def test_a_click_renders_the_entry_into_its_frame() -> None:
    """luxd raised the frame on click; the render is the whole of the runner's work.

    One render into the entry's scene, and a successful render pushes nothing
    extra — no placeholder-then-full-scene pair.
    """

    async def scenario() -> tuple[list[str], list[tuple[str, str]]]:
        ran: list[str] = []
        display = _RecordingDisplay()
        await ZSpecClickRunner(display).run(_entry(ran=ran))
        return ran, display.shows

    ran, shows = asyncio.run(scenario())

    assert ran == ["z-spec-picker"]
    assert shows == []  # a successful render pushes nothing extra


def test_a_failing_render_is_logged_and_reported_in_the_frame(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Empty project → the picker reports spec_not_found; the user must see why.

    Without inspecting the outcome the raised frame keeps whatever it held, with
    no diagnostic anywhere the user is looking.
    """

    async def scenario() -> list[tuple[str, str]]:
        display = _RecordingDisplay()
        runner = ZSpecClickRunner(display)
        with caplog.at_level(logging.WARNING):
            await runner.run(_entry(outcome=_FAILED))
        return display.shows

    shows = asyncio.run(scenario())

    # The failure lands in the frame under the very title that was clicked.
    assert shows == [("z-spec-picker", "Z-Spec Browser")]
    assert "z-spec-browse click failed" in caplog.text
    assert "No Z specs found in /work/repo" in caplog.text


def test_a_down_display_cannot_crash_the_failure_report(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def scenario() -> None:
        runner = ZSpecClickRunner(_FailingDisplay())
        with caplog.at_level(logging.WARNING):
            await runner.run(_entry(outcome=_FAILED))

    asyncio.run(scenario())

    assert "could not render error scene z-spec-picker" in caplog.text


def test_the_click_does_not_block_the_event_loop() -> None:
    """Loop-starvation guard: the blocking render is off-loaded, not run inline."""

    async def scenario() -> bool:
        latch = threading.Event()
        entered = threading.Event()

        class _BlockingCommand:
            def run(
                self, target: Path, /, *, frame_id: str, frame_title: str
            ) -> ClickOutcome:
                entered.set()
                if not latch.wait(timeout=5):
                    raise AssertionError("latch never released")
                return _OK

        def factory(_display: Display) -> ClickCommand:
            return _BlockingCommand()

        entry = ZSpecMenuEntry(
            callback_id="z-spec-browse",
            title="Z-Spec Browser",
            scene_id="z-spec-picker",
            factory=factory,
            target=_PROJECT,
        )
        runner = ZSpecClickRunner(_RecordingDisplay())
        task = asyncio.create_task(runner.run(entry))
        # If the render ran inline on the loop, this sleep could not complete until
        # the latch releases. With asyncio.to_thread the loop stays free, so
        # control returns here while the render is still blocked in the worker.
        await asyncio.sleep(0.1)
        progressed = entered.is_set() and not task.done()
        latch.set()
        await asyncio.wait_for(task, timeout=2)
        return progressed

    assert asyncio.run(scenario()) is True
