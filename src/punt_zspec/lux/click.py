"""What one menu click does: render the entry, report a failure.

``ZSpecClickRunner`` is the click itself: render off the event loop and replace
the frame with the reason when the render fails. The frame is raised by luxd
Display-locally — the callback was registered with the entry's scene as its
``frame_id`` — so the click no longer mutates the display from the client side
(punt-lux DES-088).

Nothing here runs inline on the FastMCP event loop. The render goes through
:func:`asyncio.to_thread`, so a blocking REST round-trip never starves the loop
that serves check/test/animate.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Self, final

from punt_zspec.commands.show import DisplayError

if TYPE_CHECKING:
    from punt_zspec.commands.result import CommandError
    from punt_zspec.commands.show import Display
    from punt_zspec.lux.entry import ZSpecMenuEntry

__all__ = ["ZSpecClickRunner"]

logger = logging.getLogger(__name__)


@final
class ZSpecClickRunner:
    """Run one menu entry's click: render it, report a failure into its frame."""

    _display: Display
    __slots__ = ("_display",)

    def __new__(cls, display: Display) -> Self:
        """Render clicks through ``display``."""
        self = super().__new__(cls)
        self._display = display
        return self

    async def run(self, entry: ZSpecMenuEntry) -> None:
        """Render the entry off-loop and report a failure into its frame.

        luxd raises the entry's frame on click, so the render here is the whole
        of the client's work. A failed render (empty project, unreadable spec,
        down luxd) returns a typed failure rather than raising; without
        inspecting it the user is left looking at whatever the frame held before,
        with no diagnostic. On failure the error is logged and the frame is
        replaced with the failure text.
        """
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
                frame_title=entry.title,
            )
        except DisplayError as exc:
            logger.warning("could not render error scene %s: %s", entry.scene_id, exc)
