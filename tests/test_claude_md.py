"""The §2.4 import-line contract: exact match, code blocks, byte preservation."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from punt_zspec.claude_md import ClaudeMdImport, MarkdownLines

LINE = "@.punt-labs/z-spec/CLAUDE.md"


def _host(tmp_path: Path, text: str) -> Path:
    host = tmp_path / "CLAUDE.md"
    host.write_bytes(text.encode())
    return host


def test_register_appends_one_bare_line(tmp_path: Path) -> None:
    host = _host(tmp_path, "# Project\n\nProse.\n")

    assert ClaudeMdImport(host, LINE).register()

    assert host.read_text() == f"# Project\n\nProse.\n{LINE}\n"


def test_register_is_idempotent(tmp_path: Path) -> None:
    host = _host(tmp_path, "Prose.\n")
    imp = ClaudeMdImport(host, LINE)

    assert imp.register()
    assert not imp.register()

    assert host.read_text().count(LINE) == 1


def test_register_separates_from_an_unterminated_last_line(tmp_path: Path) -> None:
    host = _host(tmp_path, "no trailing newline")

    ClaudeMdImport(host, LINE).register()

    assert host.read_text() == f"no trailing newline\n{LINE}\n"


def test_register_creates_a_missing_host(tmp_path: Path) -> None:
    host = tmp_path / "CLAUDE.md"

    assert ClaudeMdImport(host, LINE).register()

    assert host.read_text() == f"{LINE}\n"
    assert stat.S_IMODE(host.stat().st_mode) == 0o644


def test_register_preserves_crlf_endings(tmp_path: Path) -> None:
    host = _host(tmp_path, "# Project\r\n\r\nProse.\r\n")

    ClaudeMdImport(host, LINE).register()

    assert host.read_bytes() == f"# Project\r\n\r\nProse.\r\n{LINE}\r\n".encode()


def test_register_preserves_an_existing_mode(tmp_path: Path) -> None:
    host = _host(tmp_path, "Prose.\n")
    host.chmod(0o600)

    ClaudeMdImport(host, LINE).register()

    assert stat.S_IMODE(host.stat().st_mode) == 0o600


def test_register_writes_through_a_symlink(tmp_path: Path) -> None:
    real = _host(tmp_path, "Prose.\n")
    link = tmp_path / "linked.md"
    link.symlink_to(real)

    ClaudeMdImport(link, LINE).register()

    assert link.is_symlink()
    assert real.read_text() == f"Prose.\n{LINE}\n"


def test_register_keeps_non_utf8_bytes_intact(tmp_path: Path) -> None:
    host = tmp_path / "CLAUDE.md"
    host.write_bytes(b"caf\xe9\n")

    ClaudeMdImport(host, LINE).register()

    assert host.read_bytes() == b"caf\xe9\n" + f"{LINE}\n".encode()


def test_prune_removes_every_top_level_copy(tmp_path: Path) -> None:
    host = _host(tmp_path, f"A\n{LINE}\nB\n{LINE}\n")

    assert ClaudeMdImport(host, LINE).prune()

    assert host.read_text() == "A\nB\n"


def test_prune_is_a_no_op_when_absent(tmp_path: Path) -> None:
    host = _host(tmp_path, "A\n")

    assert not ClaudeMdImport(host, LINE).prune()

    assert host.read_text() == "A\n"


def test_a_fenced_copy_is_inert(tmp_path: Path) -> None:
    host = _host(tmp_path, f"```text\n{LINE}\n```\n")
    imp = ClaudeMdImport(host, LINE)

    assert not imp.is_registered()
    assert imp.register()

    assert host.read_text() == f"```text\n{LINE}\n```\n{LINE}\n"
    assert imp.prune()
    assert host.read_text() == f"```text\n{LINE}\n```\n"


def test_an_indented_copy_is_inert(tmp_path: Path) -> None:
    host = _host(tmp_path, f"    {LINE}\n")

    assert not ClaudeMdImport(host, LINE).is_registered()


def test_a_dangling_fence_does_not_swallow_the_import(tmp_path: Path) -> None:
    # An unterminated opener delimits nothing: the naive odd-count rule would
    # misread the trailing line as fenced, duplicate it, and never prune it.
    host = _host(tmp_path, f"```\nstray opener\n\n{LINE}\n")
    imp = ClaudeMdImport(host, LINE)

    assert imp.is_registered()
    assert not imp.register()
    assert imp.prune()


def test_a_shorter_inner_run_does_not_close_a_block(tmp_path: Path) -> None:
    host = _host(tmp_path, f"````\n```\n{LINE}\n````\n")

    assert not ClaudeMdImport(host, LINE).is_registered()


def test_a_tilde_run_does_not_close_a_backtick_block(tmp_path: Path) -> None:
    host = _host(tmp_path, f"```\n~~~\n{LINE}\n```\n")

    assert not ClaudeMdImport(host, LINE).is_registered()


def test_a_crlf_host_line_still_matches(tmp_path: Path) -> None:
    host = _host(tmp_path, f"A\r\n{LINE}\r\n")

    assert ClaudeMdImport(host, LINE).is_registered()


@pytest.mark.parametrize(
    "bad", ["", "   ", "@a\n@b", " @a", "@a ", ".punt-labs/z-spec/CLAUDE.md"]
)
def test_a_malformed_import_line_is_rejected(tmp_path: Path, bad: str) -> None:
    with pytest.raises(ValueError, match="import line"):
        ClaudeMdImport(tmp_path / "CLAUDE.md", bad)


def test_eol_defaults_to_lf_on_an_empty_document() -> None:
    assert MarkdownLines("").eol() == "\n"


def test_lone_cr_endings_are_preserved(tmp_path: Path) -> None:
    host = _host(tmp_path, "A\rB\r")

    ClaudeMdImport(host, LINE).register()

    assert host.read_bytes() == f"A\rB\r{LINE}\r".encode()


def test_the_lock_is_the_mandated_tool_agnostic_sibling(tmp_path: Path) -> None:
    host = _host(tmp_path, "A\n")

    ClaudeMdImport(host, LINE).register()

    assert (tmp_path / ".CLAUDE.md.punt-import.lock").is_file()


def test_a_failed_write_leaves_no_temp_file(tmp_path: Path) -> None:
    host = _host(tmp_path, "A\n")
    ClaudeMdImport(host, LINE).register()

    assert not [p for p in tmp_path.iterdir() if p.name.endswith(".tmp")]


def test_the_host_directory_is_created_on_demand(tmp_path: Path) -> None:
    host = tmp_path / "nested" / "CLAUDE.md"

    ClaudeMdImport(host, LINE).register()

    assert host.read_text() == f"{LINE}\n"
    assert os.path.isdir(tmp_path / "nested")
