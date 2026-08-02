"""The one gate: the MCP surface answers only where the marker is present."""

from __future__ import annotations

import json
from pathlib import Path

from punt_zspec.commands.enable import EnableCommand
from punt_zspec.commands.gate import EnablementGate


def _ok() -> str:
    """A stand-in tool that succeeds whenever the gate lets it run."""
    return '{"ok": true}'


def _bare_repo(tmp_path: Path) -> Path:
    (tmp_path / ".git").mkdir()
    (tmp_path / "CLAUDE.md").write_text("# Project\n", encoding="utf-8")
    return tmp_path


def test_a_repo_with_no_marker_is_shut(tmp_path: Path) -> None:
    assert not EnablementGate(_bare_repo(tmp_path)).is_open()


def test_a_repo_with_the_marker_is_open(tmp_path: Path) -> None:
    root = _bare_repo(tmp_path)
    EnableCommand().run(root)

    assert EnablementGate(root).is_open()


def test_disabling_shuts_the_gate_again(tmp_path: Path) -> None:
    from punt_zspec.commands.disable import DisableCommand

    root = _bare_repo(tmp_path)
    gate = EnablementGate(root)
    EnableCommand().run(root)

    DisableCommand().run(root)

    assert not gate.is_open()


def test_outside_a_repository_the_gate_is_shut(tmp_path: Path) -> None:
    assert not EnablementGate(Path(tmp_path.anchor)).is_open()


def test_the_refusal_names_the_enable_command(tmp_path: Path) -> None:
    wire = json.loads(EnablementGate(_bare_repo(tmp_path)).decline())

    assert wire["ok"] is False
    assert "z-spec enable" in wire["error"]
    assert "/z-spec:enable" in wire["error"]


def test_guard_declines_without_calling_the_tool(tmp_path: Path) -> None:
    calls: list[str] = []

    def tool(file: str) -> str:
        calls.append(file)
        return '{"ok": true}'

    gated = EnablementGate(_bare_repo(tmp_path)).guard(tool)

    assert json.loads(gated("s.tex"))["ok"] is False
    assert calls == []


def test_guard_never_self_enables(tmp_path: Path) -> None:
    # §2.3: an invocation in an unmarked repo is a graceful no-op, never a
    # trigger to write the marker the user did not ask for.
    root = _bare_repo(tmp_path)
    gated = EnablementGate(root).guard(_ok)

    gated()

    assert not (root / ".punt-labs").exists()


def test_guard_passes_through_once_the_marker_exists(tmp_path: Path) -> None:
    def echo(file: str) -> str:
        return f'{{"file": "{file}"}}'

    root = _bare_repo(tmp_path)
    gated = EnablementGate(root).guard(echo)
    EnableCommand().run(root)

    assert json.loads(gated("s.tex"))["file"] == "s.tex"


def test_guard_reads_the_marker_on_every_call(tmp_path: Path) -> None:
    # No caching: enabling mid-session must take effect on the next call, not
    # on the next server restart.
    root = _bare_repo(tmp_path)
    gated = EnablementGate(root).guard(_ok)
    assert json.loads(gated())["ok"] is False

    EnableCommand().run(root)

    assert json.loads(gated())["ok"] is True


def test_guard_keeps_the_name_and_docstring_fastmcp_reads(tmp_path: Path) -> None:
    def check(file: str) -> str:
        """Type-check a Z specification."""
        return file

    gated = EnablementGate(_bare_repo(tmp_path)).guard(check)

    assert gated.__name__ == "check"
    assert gated.__doc__ == "Type-check a Z specification."
