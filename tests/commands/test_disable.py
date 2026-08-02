"""The ``disable`` verb: non-destructive, and idempotent (§2.3, §2.9)."""

from __future__ import annotations

import json
from pathlib import Path

from punt_zspec.commands.disable import DisableCommand
from punt_zspec.commands.enable import EnableCommand
from punt_zspec.commands.enablement import IMPORT_LINE
from punt_zspec.commands.result import CommandFailure


def _enabled_repo(tmp_path: Path) -> Path:
    (tmp_path / ".git").mkdir()
    (tmp_path / "CLAUDE.md").write_text("# Project\n")
    EnableCommand().run(tmp_path)
    return tmp_path


def test_disable_reports_the_repo_as_disabled(tmp_path: Path) -> None:
    root = _enabled_repo(tmp_path)

    report = DisableCommand().run(root).unwrap()

    assert not report.enabled
    assert not report.marker.exists()
    assert IMPORT_LINE not in (root / "CLAUDE.md").read_text()


def test_disable_leaves_the_subtree_dormant(tmp_path: Path) -> None:
    root = _enabled_repo(tmp_path)

    report = DisableCommand().run(root).unwrap()

    assert report.guide.is_file()


def test_disable_on_a_never_enabled_repo_is_a_no_op(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "CLAUDE.md").write_text("# Project\n")

    report = DisableCommand().run(tmp_path).unwrap()

    assert not report.enabled
    assert (tmp_path / "CLAUDE.md").read_text() == "# Project\n"


def test_disable_outside_a_repository_fails_cleanly(tmp_path: Path) -> None:
    result = DisableCommand().run(Path(tmp_path.anchor))

    err = result.error
    assert err is not None
    assert err.kind is CommandFailure.not_a_repository


def test_the_json_wire_form_carries_the_verb_and_the_state(tmp_path: Path) -> None:
    root = _enabled_repo(tmp_path)

    wire = json.loads(DisableCommand().run(root).to_json())

    assert wire["ok"] is True
    assert wire["action"] == "disable"
    assert wire["enabled"] is False
