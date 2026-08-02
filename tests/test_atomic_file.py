"""The §2.4 write contract: locked, atomic, byte-preserving host-file writes."""

from __future__ import annotations

import stat
from pathlib import Path

from punt_zspec.atomic_file import AtomicFile


def test_read_of_a_missing_file_is_empty(tmp_path: Path) -> None:
    assert AtomicFile(tmp_path / "absent.json").read() == ""


def test_write_then_read_round_trips_every_ending(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    text = "lf\ncrlf\r\ncr\rend"

    AtomicFile(path).write(text)

    assert AtomicFile(path).read() == text
    assert path.read_bytes() == text.encode()


def test_write_replaces_rather_than_truncates(tmp_path: Path) -> None:
    path = tmp_path / "host.md"
    path.write_text("original, longer content\n")

    AtomicFile(path).write("short\n")

    assert path.read_text() == "short\n"


def test_a_new_file_gets_mode_0644(tmp_path: Path) -> None:
    path = tmp_path / "fresh.md"

    AtomicFile(path).write("x\n")

    assert stat.S_IMODE(path.stat().st_mode) == 0o644


def test_the_lock_names_the_sibling_not_the_target(tmp_path: Path) -> None:
    path = tmp_path / "CLAUDE.md"

    with AtomicFile(path).locked():
        pass

    assert (tmp_path / ".CLAUDE.md.punt-import.lock").is_file()
    assert not path.exists()


def test_path_is_the_host_it_was_given(tmp_path: Path) -> None:
    path = tmp_path / "CLAUDE.md"

    assert AtomicFile(path).path == path
