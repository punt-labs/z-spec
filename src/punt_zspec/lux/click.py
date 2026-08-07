"""What one menu click does: raise the entry's frame, render it, report a failure.

``ZSpecFrameRaiser`` is the guarded transport for the Hub's ``raise_frame`` —
the same best-effort discipline ``ZSpecMenuRegistrar`` holds over
``register_callback``. ``ZSpecClickRunner`` is the click itself: raise first for
an instant response, then render off the event loop, and replace the frame with
the reason when the render fails.

Nothing here runs inline on the FastMCP event loop. The raise and the render both
go through :func:`asyncio.to_thread`, so a blocking REST round-trip never starves
the loop that serves check/test/animate.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Self, final

from punt_lux import HubUnavailableError
from punt_lux.operations import OpError

from punt_zspec.commands.show import DisplayError

if TYPE_CHECKING:
    from collections.abc import Callable

    from punt_zspec.commands.result import CommandError
    from punt_zspec.commands.show import Display
    from punt_zspec.lux.entry import ZSpecMenuEntry
    from punt_zspec.lux.ports import FrameRaiseClient

__all__ = ["ZSpecClickRunner", "ZSpecFrameRaiser"]

logger = logging.getLogger(__name__)


@final
class ZSpecFrameRaiser:
    """Bring one Hub frame to the front over the REST client, failure-tolerant."""

    _connect: Callable[[], FrameRaiseClient]
    __slots__ = ("_connect",)

    def __new__(cls, connect: Callable[[], FrameRaiseClient]) -> Self:
        self = super().__new__(cls)
        self._connect = connect
        return self

    async def raise_frame(self, frame_id: str) -> None:
        """Raise ``frame_id`` off-thread, dropping any lux failure.

        A best-effort REST I/O boundary (PY-EH-6): a down luxd logs a warning, any
        other transport fault is logged with its traceback, and neither is raised
        — the full render follows this call, and losing it to a failed raise would
        turn a slow click into a dead one. A frame the display does not hold
        answers ``raised`` false rather than erroring; that is the cold path, and
        the render behind it is what puts the frame up.
        """
        try:
            client = await asyncio.to_thread(self._connect)
            result = await asyncio.to_thread(client.raise_frame, frame_id)
        except HubUnavailableError:
            logger.warning("luxd unavailable; frame %s not raised", frame_id)
            return
        except Exception:
            logger.exception("[lux] raising frame %s failed", frame_id)
            return
        if isinstance(result, OpError):
            logger.warning("luxd refused to raise %s: %s", frame_id, result.reason)


@final
class ZSpecClickRunner:
    """Run one menu entry's click: raise its frame, render it, report a failure."""

    _display: Display
    _raiser: ZSpecFrameRaiser
    __slots__ = ("_display", "_raiser")

    def __new__(cls, display: Display, raiser: ZSpecFrameRaiser) -> Self:
        self = super().__new__(cls)
        self._display = display
        self._raiser = raiser
        return self

    async def run(self, entry: ZSpecMenuEntry) -> None:
        """Raise the entry's frame, render it off-loop, and report a failure.

        A failed render (empty project, unreadable spec, down luxd) returns a
        typed failure rather than raising; without inspecting it the user is left
        looking at whatever the frame held before, with no diagnostic. On failure
        the error is logged and the frame is replaced with the failure text.
        """
        await self._raiser.raise_frame(entry.scene_id)
        outcome = await asyncio.to_thread(entry.run, self._display)
        error = outcome.error
        if error is not None:
            logger.warning(
                "[lux] %s click failed: %s", entry.callback_id, error.message
            )
            await self._report(entry, error)

    async def _report(self, entry: ZSpecMenuEntry, error: CommandError) -> None:
        """Render the failure text into the entry's own frame (off-thread)."""
        try:
            await asyncio.to_thread(
                self._display.show,
                entry.error_scene(error),
                frame_id=entry.scene_id,
                frame_title=entry.scene_title,
            )
        except DisplayError as exc:
            logger.warning("could not render error scene %s: %s", entry.scene_id, exc)
