"""The menu-title invariant: a click lands in a frame named for the label clicked.

``ZSpecMenuEntry`` carries one ``title`` and hands it to the command as the frame
title, so the label luxd registers and the name the frame ends up with are one
string travelling one path. This asserts that path end to end: each shipped entry
runs against its real target and the title reaching ``Display.show`` is compared
with the title the entry was registered under.

The invariant used to rest on data agreeing — the manifest's collection title
happening to equal the Tutorial leaf's label. It no longer does, which is why the
manifest is back to its own authored title; the structure carries it instead. The
test is unchanged because it always asserted the property, never the mechanism.

Nothing is faked but the display: the manifest, the ten lesson specs, and the
commands are the shipped ones.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from punt_zspec.browser import build_browser_scene
from punt_zspec.commands.browse import BrowseCommand
from punt_zspec.lux.entry import ZSpecMenuEntries

if TYPE_CHECKING:
    from punt_zspec.commands.show import Display
    from punt_zspec.lux.entry import ZSpecMenuEntry

# The dev-checkout half of what ZSpecLuxSession._default_tutorial_manifest
# resolves at runtime: it prefers $ZSPEC_PLUGIN_ROOT (injected by plugin.json in
# an installed plugin) and falls back to <repo>/plugin. Spelled out rather than
# called, because reaching for a private resolver would let this test agree with
# a broken one. If that fallback moves, this constant has to move with it.
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


def test_browsing_the_shipped_collection_still_shows_its_own_title() -> None:
    """Off the menu path there is no override, so the manifest names its frame.

    The menu is the only caller that renames a frame. The ``browse`` tool and the
    CLI verb must still report and show the title the manifest actually authors —
    the thing that stopped being true when the collection was renamed to match a
    menu leaf.
    """
    titles: list[str] = []

    result = BrowseCommand(
        build=build_browser_scene, display=_recording_display(titles)
    ).run(_MANIFEST)

    assert result.unwrap().title == "Introduction to Z Notation"
    assert titles == ["Introduction to Z Notation"]
