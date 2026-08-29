"""z-spec's menu entries: one entry's identity and behavior, and the two it ships.

``ZSpecMenuEntry`` is one leaf of the lux Clients menu — a callback id, a title,
the Hub scene it raises, the shipped command a click runs. ``ZSpecMenuEntries``
is the pair z-spec registers, and the one place all of that is decided.

One ``title`` field does two jobs: the label luxd shows in the menu, and the title
of the frame a click on it raises. Two fields would be two names for one thing,
free to drift; one cannot. The title carries the tool's name because the submenu
around it names the repository, not the client.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, final

from punt_lux.protocol import TextElement

from punt_zspec.browser import build_browser_scene, build_spec_picker
from punt_zspec.commands.browse import BrowseCommand
from punt_zspec.commands.picker import PickerCommand

if TYPE_CHECKING:
    from pathlib import Path

    from punt_zspec.commands.result import CommandError
    from punt_zspec.commands.show import Display
    from punt_zspec.lux.command_ports import (
        ClickCommand,
        ClickCommandFactory,
        ClickOutcome,
    )

__all__ = ["ZSpecMenuEntries", "ZSpecMenuEntry"]


@final
@dataclass(frozen=True, slots=True)
class ZSpecMenuEntry:
    """One menu entry: its callback id, title, scene, and the command it runs.

    ``scene_id`` is both the id the click raises and the ``frame_id`` its command
    renders into — one Hub scene, so a raise brings up the very frame the render
    then refreshes. ``target`` is the command's argument (manifest or directory).
    """

    callback_id: str
    title: str
    scene_id: str
    factory: ClickCommandFactory
    target: Path

    def matches(self, callback_id: str) -> bool:
        """Return whether a click's ``callback_id`` selects this entry."""
        return self.callback_id == callback_id

    def run(self, display: Display) -> ClickOutcome:
        """Run this entry's command on ``display`` and return its outcome.

        Blocking — call off-thread. The command captures a down display as a
        typed failure rather than raising; the caller reads the returned outcome
        to report a render the user would otherwise wait on forever.
        """
        return self.factory(display).run(self.target, frame_id=self.scene_id)

    def error_scene(self, error: CommandError) -> TextElement:
        """Return the scene that reports a render this entry could not complete."""
        return TextElement(
            id=f"{self.scene_id}-error",
            content=f"{self.title} failed: {error.message}",
        )


@final
class ZSpecMenuEntries:
    """The two entries z-spec registers, and everything that names them."""

    __slots__ = ()

    @classmethod
    def of(
        cls, *, tutorial_manifest: Path, browse_root: Path
    ) -> tuple[ZSpecMenuEntry, ...]:
        """Return the Tutorial and Browse entries in the order they register.

        Each title names the frame its click raises: Browse reads that name off
        ``PickerCommand``, while Tutorial's frame is named by the shipped
        manifest's collection title, which no import reaches — a test compares it.
        """
        return (
            ZSpecMenuEntry(
                callback_id="z-spec-tutorial",
                title="Z-Spec Tutorial",
                scene_id="z-spec-tutorial",
                factory=cls._tutorial,
                target=tutorial_manifest,
            ),
            ZSpecMenuEntry(
                callback_id="z-spec-browse",
                title=PickerCommand.FRAME_TITLE,
                scene_id="z-spec-picker",
                factory=cls._picker,
                target=browse_root,
            ),
        )

    @staticmethod
    def _tutorial(display: Display) -> ClickCommand:
        """Build the Tutorial command: the browser over the shipped manifest."""
        return BrowseCommand(build=build_browser_scene, display=display)

    @staticmethod
    def _picker(display: Display) -> ClickCommand:
        """Build the Browse command: the picker over the user's project."""
        return PickerCommand(build=build_spec_picker, display=display)
