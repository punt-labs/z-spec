"""Tests for the menu entries z-spec ships — how they read and what they run."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from punt_zspec.commands.browse import BrowseCommand
from punt_zspec.commands.picker import PickerCommand, PickerResult
from punt_zspec.commands.result import CommandError, CommandFailure, CommandResult
from punt_zspec.lux.entry import ZSpecMenuEntries, ZSpecMenuEntry

if TYPE_CHECKING:
    from punt_zspec.lux.command_ports import ClickCommand, ClickOutcome

_MANIFEST = Path("/plugin/tutorials/intro/manifest.toml")
_PROJECT = Path("/work/repo")


class _RecordingDisplay:
    """A Display that records nothing — the entries here never render."""

    def show(self, scene: object, *, frame_id: str, frame_title: str) -> None:
        raise AssertionError("no entry test renders")


def _entries() -> tuple[ZSpecMenuEntry, ...]:
    return ZSpecMenuEntries.of(tutorial_manifest=_MANIFEST, browse_root=_PROJECT)


def test_the_two_entries_are_titled_with_the_tool_and_the_applet() -> None:
    # The submenu around them names the repository, not the client, so the tool's
    # own name has to travel on the leaf or it appears nowhere in the menu path.
    tutorial, browse = _entries()

    assert (tutorial.title, browse.title) == ("Z-Spec Tutorial", "Z-Spec Browser")


def test_each_entry_carries_its_callback_id_scene_and_target() -> None:
    tutorial, browse = _entries()

    assert (tutorial.callback_id, tutorial.scene_id) == (
        "z-spec-tutorial",
        "z-spec-tutorial",
    )
    assert (browse.callback_id, browse.scene_id) == ("z-spec-browse", "z-spec-picker")
    assert (tutorial.target, browse.target) == (_MANIFEST, _PROJECT)


def test_the_tutorial_entry_runs_the_browser_and_browse_runs_the_picker() -> None:
    # Each entry is one more caller of a shipped command, so the menu holds no
    # render logic of its own.
    tutorial, browse = _entries()
    display = _RecordingDisplay()

    tutorial_command: ClickCommand = tutorial.factory(display)
    browse_command: ClickCommand = browse.factory(display)

    assert isinstance(tutorial_command, BrowseCommand)
    assert isinstance(browse_command, PickerCommand)


def test_an_entry_matches_only_its_own_callback_id() -> None:
    tutorial, browse = _entries()

    assert tutorial.matches("z-spec-tutorial")
    assert not tutorial.matches("z-spec-browse")
    assert browse.matches("z-spec-browse")


def test_run_renders_the_target_into_its_own_scene() -> None:
    ran: list[tuple[Path, str]] = []
    outcome: ClickOutcome = CommandResult.ok(
        PickerResult(total=1, scene_id="z-spec-picker")
    )

    class _Command:
        def run(self, target: Path, /, *, frame_id: str) -> ClickOutcome:
            ran.append((target, frame_id))
            return outcome

    entry = ZSpecMenuEntry(
        callback_id="z-spec-browse",
        title="Z-Spec Browser",
        scene_id="z-spec-picker",
        factory=lambda _display: _Command(),
        target=_PROJECT,
    )

    assert entry.run(_RecordingDisplay()) is outcome
    # One Hub scene: the id a click raises is the frame the command renders into.
    assert ran == [(_PROJECT, "z-spec-picker")]


def test_the_error_scene_names_the_entry_and_the_reason() -> None:
    _, browse = _entries()
    error = CommandError(
        CommandFailure.spec_not_found, "No Z specs found in /work/repo"
    )

    scene = browse.error_scene(error)

    assert scene.id == "z-spec-picker-error"
    assert scene.content == "Z-Spec Browser failed: No Z specs found in /work/repo"
