"""The menu-title invariant: a click lands in a frame named for the label clicked.

``ZSpecMenuEntry`` carries one ``title``, so the label luxd shows and the title
the click path renders cannot diverge inside the entry. What no type ties down is
the far end — the frame is titled by whatever the entry's *command* decides: the
shipped manifest's collection title for Tutorial, ``PickerCommand.FRAME_TITLE``
for Browse. So each shipped entry is run here against its real target, and the
title it puts on screen is compared with the title it was registered under.

Nothing is faked but the display. The manifest, the ten lesson specs, and the
commands are the shipped ones, because the drift this guards against lives
exactly in the data a fake would replace.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from punt_zspec.lux.entry import ZSpecMenuEntries

if TYPE_CHECKING:
    from punt_zspec.commands.show import Display
    from punt_zspec.lux.entry import ZSpecMenuEntry

_TUTORIAL = Path(__file__).resolve().parents[2] / "plugin" / "tutorials" / "intro"
_MANIFEST = _TUTORIAL / "manifest.toml"


def _recording_display(titles: list[str]) -> Display:
    class _Rec:
        def show(self, scene: object, *, frame_id: str, frame_title: str) -> None:
            titles.append(frame_title)

    return _Rec()


def _shipped_entry(callback_id: str) -> ZSpecMenuEntry:
    """Return the shipped entry ``callback_id`` selects, browsing the lesson specs.

    The tutorial directory doubles as the Browse target so both entries run over
    real files: the picker discovers the same specs the manifest lists.
    """
    entries = ZSpecMenuEntries.of(tutorial_manifest=_MANIFEST, browse_root=_TUTORIAL)
    return next(entry for entry in entries if entry.matches(callback_id))


@pytest.mark.parametrize("callback_id", ["z-spec-tutorial", "z-spec-browse"])
def test_a_click_renders_a_frame_titled_with_the_label_that_was_clicked(
    callback_id: str,
) -> None:
    titles: list[str] = []
    entry = _shipped_entry(callback_id)

    outcome = entry.run(_recording_display(titles))

    assert outcome.error is None, "the shipped target must render"
    assert titles == [entry.title]
