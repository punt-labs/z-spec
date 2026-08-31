"""``gen_dev_commands --check`` must gate both legitimate tree states.

The working tree carries generated ``-dev`` twins beside every prod command
(plugin name ``z-spec-dev``); a release-swapped tree carries none (plugin
name ``z-spec``). Each state has its own failure mode — a missing twin in
the dev tree, a leftover twin in the prod tree — and the checker must fail
on both while passing both healthy states. A checker that only knew the
dev tree failed every release PR the moment the prod swap deleted the
twins.

The tool is driven as a subprocess, the same way the Makefile invokes it,
so the tests cover the real entry point rather than an imported internal.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Final, final

_TOOL: Final[Path] = (
    Path(__file__).resolve().parent.parent / "tools" / "gen_dev_commands.py"
)
_PROD_BODY: Final[str] = "# /z-spec:check\nRun mcp__plugin_z-spec_zspec__check.\n"


@final
class PluginTree:
    """A scratch plugin tree in one of the checker's recognized states."""

    _commands: Path
    __slots__ = ("_commands",)

    def __new__(cls, root: Path, name: str, *, twins: bool) -> PluginTree:
        self = super().__new__(cls)
        self._commands = root / "plugin" / "commands"
        self._commands.mkdir(parents=True)
        manifest_dir = root / "plugin" / ".claude-plugin"
        manifest_dir.mkdir()
        (manifest_dir / "plugin.json").write_text(
            json.dumps({"name": name}), encoding="utf-8"
        )
        (self._commands / "check.md").write_text(_PROD_BODY, encoding="utf-8")
        if twins:
            self._run("--write")
        return self

    def _run(self, mode: str) -> int:
        result = subprocess.run(
            [sys.executable, str(_TOOL), str(self._commands), mode],
            capture_output=True,
            check=False,
        )
        return result.returncode

    def check(self) -> int:
        """Return the checker's exit code for this tree."""
        return self._run("--check")

    def remove(self, filename: str) -> None:
        """Delete one command file from the tree."""
        (self._commands / filename).unlink()

    def add_twin(self, filename: str) -> None:
        """Plant a dev twin, as a leftover the release swap failed to delete."""
        (self._commands / filename).write_text(_PROD_BODY, encoding="utf-8")


def test_dev_tree_with_twins_in_sync_passes(tmp_path: Path) -> None:
    assert PluginTree(tmp_path, "z-spec-dev", twins=True).check() == 0


def test_dev_tree_missing_twin_fails(tmp_path: Path) -> None:
    tree = PluginTree(tmp_path, "z-spec-dev", twins=True)
    tree.remove("check-dev.md")
    assert tree.check() == 1


def test_prod_tree_without_twins_passes(tmp_path: Path) -> None:
    assert PluginTree(tmp_path, "z-spec", twins=False).check() == 0


def test_prod_tree_with_leftover_twin_fails(tmp_path: Path) -> None:
    tree = PluginTree(tmp_path, "z-spec", twins=False)
    tree.add_twin("check-dev.md")
    assert tree.check() == 1


def test_unknown_plugin_name_fails_loud(tmp_path: Path) -> None:
    assert PluginTree(tmp_path, "someone-elses-plugin", twins=False).check() == 2
