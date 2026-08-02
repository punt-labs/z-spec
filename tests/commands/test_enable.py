"""The ``enable`` verb: idempotent, and the upgrade path (§2.3)."""

from __future__ import annotations

import json
from pathlib import Path

from punt_zspec.commands.enable import EnableCommand
from punt_zspec.commands.enablement import IMPORT_LINE
from punt_zspec.commands.result import CommandFailure


def _repo(tmp_path: Path) -> Path:
    (tmp_path / ".git").mkdir()
    (tmp_path / "CLAUDE.md").write_text("# Project\n")
    return tmp_path


def test_enable_reports_the_repo_as_enabled(tmp_path: Path) -> None:
    root = _repo(tmp_path)

    report = EnableCommand().run(root).unwrap()

    assert report.enabled
    assert report.root == root.resolve()
    assert report.marker == root / ".punt-labs" / "z-spec" / "enabled"
    assert report.import_line == IMPORT_LINE


def test_enable_writes_all_three_artifacts(tmp_path: Path) -> None:
    root = _repo(tmp_path)

    report = EnableCommand().run(root).unwrap()

    assert report.marker.is_file()
    assert report.guide.is_file()
    assert IMPORT_LINE in (root / "CLAUDE.md").read_text()


def test_enable_twice_adds_the_import_line_once(tmp_path: Path) -> None:
    root = _repo(tmp_path)

    EnableCommand().run(root)
    EnableCommand().run(root)

    assert (root / "CLAUDE.md").read_text().count(IMPORT_LINE) == 1


def test_enable_works_from_a_subdirectory(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    nested = root / "src"
    nested.mkdir()

    report = EnableCommand().run(nested).unwrap()

    assert report.root == root.resolve()


def test_enable_outside_a_repository_fails_cleanly(tmp_path: Path) -> None:
    result = EnableCommand().run(Path(tmp_path.anchor))

    err = result.error
    assert err is not None
    assert err.kind is CommandFailure.not_a_repository
    assert "not inside a git repository" in err.message


def test_the_json_wire_form_carries_the_verb_and_the_state(tmp_path: Path) -> None:
    root = _repo(tmp_path)

    wire = json.loads(EnableCommand().run(root).to_json())

    assert wire["ok"] is True
    assert wire["action"] == "enable"
    assert wire["enabled"] is True
