"""Tests for the click path: raise the entry's frame, render it, report a failure.

No live Hub — a fake REST client stands in for ``raise_frame`` and a fake Display
for the render. Async tests run on a throwaway loop via ``asyncio.run``.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from pathlib import Path
from typing import TYPE_CHECKING

from punt_lux import HubUnavailableError
from punt_lux.operations import FrameRaise, OpError

from punt_zspec.commands.picker import PickerResult
from punt_zspec.commands.result import CommandError, CommandFailure, CommandResult
from punt_zspec.commands.show import DisplayError
from punt_zspec.lux.click import ZSpecClickRunner, ZSpecFrameRaiser
from punt_zspec.lux.entry import ZSpecMenuEntry

if TYPE_CHECKING:
    import pytest

    from punt_zspec.commands.show import Display
    from punt_zspec.lux.command_ports import ClickCommand, ClickOutcome
    from punt_zspec.lux.ports import FrameRaiseClient

_PROJECT = Path("/work/repo")
_OK: ClickOutcome = CommandResult.ok(PickerResult(total=1, scene_id="z-spec-picker"))
_FAILED: ClickOutcome = CommandResult[PickerResult].failed(
    CommandError(CommandFailure.spec_not_found, "No Z specs found in /work/repo")
)


class _RecordingRaiseClient:
    """A FrameRaiseClient that records each frame it was asked to raise."""

    def __init__(self, raised: bool = True) -> None:
        self.frames: list[str] = []
        self._raised = raised

    def raise_frame(self, frame_id: str) -> FrameRaise | OpError:
        self.frames.append(frame_id)
        return FrameRaise(frame_id=frame_id, raised=self._raised)


class _RefusingRaiseClient:
    """A FrameRaiseClient whose raise is refused with a typed error."""

    def raise_frame(self, frame_id: str) -> FrameRaise | OpError:
        return OpError(code="not_found", reason=f"unknown frame {frame_id}")


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
        def run(self, target: Path, /, *, frame_id: str) -> ClickOutcome:
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


def _runner(display: Display, client: FrameRaiseClient) -> ZSpecClickRunner:
    return ZSpecClickRunner(display, ZSpecFrameRaiser(lambda: client))


def test_a_click_raises_the_entrys_frame_then_renders_into_it() -> None:
    """The raise is the instant half of the answer; the render follows it.

    One Hub call, not the placeholder-then-full-scene pair 0.22 needed — the
    frame the raise brings up is the frame the render then refreshes.
    """

    async def scenario() -> tuple[list[str], list[str], list[tuple[str, str]]]:
        ran: list[str] = []
        client = _RecordingRaiseClient()
        display = _RecordingDisplay()
        await _runner(display, client).run(_entry(ran=ran))
        return client.frames, ran, display.shows

    frames, ran, shows = asyncio.run(scenario())

    assert frames == ["z-spec-picker"]
    assert ran == ["z-spec-picker"]
    assert shows == []  # a successful render pushes nothing extra


def test_a_cold_frame_is_not_an_error() -> None:
    """``raised`` false is a fact, not a failure — the render behind it puts it up."""

    async def scenario() -> list[str]:
        ran: list[str] = []
        await _runner(_RecordingDisplay(), _RecordingRaiseClient(raised=False)).run(
            _entry(ran=ran)
        )
        return ran

    assert asyncio.run(scenario()) == ["z-spec-picker"]


def test_a_down_luxd_does_not_stop_the_render(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Losing the render to a failed raise would turn a slow click into a dead one."""

    def down() -> FrameRaiseClient:
        raise HubUnavailableError("luxd not running")

    async def scenario() -> list[str]:
        ran: list[str] = []
        runner = ZSpecClickRunner(_RecordingDisplay(), ZSpecFrameRaiser(down))
        with caplog.at_level(logging.WARNING):
            await runner.run(_entry(ran=ran))
        return ran

    assert asyncio.run(scenario()) == ["z-spec-picker"]
    assert "frame z-spec-picker not raised" in caplog.text


def test_a_refused_raise_is_logged_and_the_render_still_runs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def scenario() -> list[str]:
        ran: list[str] = []
        runner = _runner(_RecordingDisplay(), _RefusingRaiseClient())
        with caplog.at_level(logging.WARNING):
            await runner.run(_entry(ran=ran))
        return ran

    assert asyncio.run(scenario()) == ["z-spec-picker"]
    assert "luxd refused to raise z-spec-picker" in caplog.text


def test_a_raise_that_blows_up_is_logged_with_its_traceback(
    caplog: pytest.LogCaptureFixture,
) -> None:
    class _Exploding:
        def raise_frame(self, frame_id: str) -> FrameRaise | OpError:
            raise OSError("connection reset")

    async def scenario() -> list[str]:
        ran: list[str] = []
        with caplog.at_level(logging.ERROR):
            await _runner(_RecordingDisplay(), _Exploding()).run(_entry(ran=ran))
        return ran

    assert asyncio.run(scenario()) == ["z-spec-picker"]
    assert "raising frame z-spec-picker failed" in caplog.text


def test_a_failing_render_is_logged_and_reported_in_the_frame(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Empty project → the picker reports spec_not_found; the user must see why.

    Without inspecting the outcome the raised frame keeps whatever it held, with
    no diagnostic anywhere the user is looking.
    """

    async def scenario() -> list[tuple[str, str]]:
        display = _RecordingDisplay()
        runner = _runner(display, _RecordingRaiseClient())
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
        runner = _runner(_FailingDisplay(), _RecordingRaiseClient())
        with caplog.at_level(logging.WARNING):
            await runner.run(_entry(outcome=_FAILED))

    asyncio.run(scenario())

    assert "could not render error scene z-spec-picker" in caplog.text


def test_the_click_does_not_block_the_event_loop() -> None:
    """Loop-starvation guard: the blocking raise is off-loaded, not run inline."""

    async def scenario() -> bool:
        latch = threading.Event()
        entered = threading.Event()

        class _BlockingRaiseClient:
            def raise_frame(self, frame_id: str) -> FrameRaise | OpError:
                entered.set()
                if not latch.wait(timeout=5):
                    raise AssertionError("latch never released")
                return FrameRaise(frame_id=frame_id, raised=True)

        runner = _runner(_RecordingDisplay(), _BlockingRaiseClient())
        task = asyncio.create_task(runner.run(_entry()))
        # If the raise ran inline on the loop, this sleep could not complete until
        # the latch releases. With asyncio.to_thread the loop stays free, so
        # control returns here while the raise is still blocked in the worker.
        await asyncio.sleep(0.1)
        progressed = entered.is_set() and not task.done()
        latch.set()
        await asyncio.wait_for(task, timeout=2)
        return progressed

    assert asyncio.run(scenario()) is True
