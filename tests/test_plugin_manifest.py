"""Static invariants on the shipped plugin manifest.

Claude Code auto-loads every plugin's ``hooks/hooks.json`` by convention; the
``manifest.hooks`` field is for *additional* hook files only. Redeclaring the
same path in the manifest makes ``claude plugin list`` refuse the plugin with
a duplicate-hooks error, taking every slash command and hook down with it.

These checks catch that class of manifest bug at ``make check`` time —
statically, without needing the ``claude`` CLI or a running Claude Code
session. Closes the invisible-bug window that let #106 ship in 0.18.0.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
_PLUGIN_ROOT: Final[Path] = _REPO_ROOT / "plugin"
_MANIFEST: Final[Path] = _PLUGIN_ROOT / ".claude-plugin" / "plugin.json"
_AUTO_HOOKS: Final[Path] = _PLUGIN_ROOT / "hooks" / "hooks.json"

# All spellings that resolve to the auto-loaded hooks/hooks.json.
_AUTO_HOOKS_ALIASES: Final[frozenset[str]] = frozenset(
    {
        "hooks/hooks.json",
        "./hooks/hooks.json",
        str(_AUTO_HOOKS),
    }
)


def test_manifest_exists_and_parses() -> None:
    assert _MANIFEST.is_file(), f"plugin manifest missing: {_MANIFEST}"
    json.loads(_MANIFEST.read_text(encoding="utf-8"))


def test_manifest_does_not_redeclare_auto_loaded_hooks() -> None:
    """The exact bug that broke z-spec@punt-labs from 0.18.0 through 0.19.0.

    Whenever ``plugin/hooks/hooks.json`` exists, Claude Code loads it
    automatically. A ``"hooks"`` entry in ``plugin.json`` pointing at that
    same file makes Claude Code see it twice and refuse the plugin. Every
    other punt-labs plugin that ships a ``hooks/hooks.json`` (biff, ethos,
    lux, quarry, vox) omits the manifest ``hooks`` field entirely; z-spec
    was the outlier.
    """
    if not _AUTO_HOOKS.is_file():
        return
    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    hooks_field = manifest.get("hooks")
    assert hooks_field not in _AUTO_HOOKS_ALIASES, (
        f"plugin.json declares hooks={hooks_field!r}, which redeclares the "
        f"auto-loaded hooks/hooks.json and makes Claude Code refuse the "
        f"plugin with a duplicate-hooks error. Drop the field; the file "
        f"loads by convention. See #106."
    )
