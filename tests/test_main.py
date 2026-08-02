"""End-to-end CLI tests for the partition, audit, show, and browse verbs."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from punt_zspec.__main__ import app
from punt_zspec.commands.show import DisplayError

if TYPE_CHECKING:
    from collections.abc import Iterator

_RUNNER = CliRunner()

_VALID_PARTITION = '{"operations": []}'
_VALID_AUDIT = '{"constraints": [], "uncovered": []}'


@pytest.fixture
def spec(tmp_path: Path) -> Path:
    """Return an existing ``.tex`` spec the CLI can read."""
    path = tmp_path / "s.tex"
    path.write_text("\\begin{zed} S == \\emptyset \\end{zed}\n", encoding="utf-8")
    return path


class _FailingDisplay:
    """A display whose render always fails — drives the display_failed path."""

    def show(self, scene: object, *, frame_id: str, frame_title: str) -> None:
        raise DisplayError("lux down")


def _make_failing_display(*_args: object, **_kwargs: object) -> _FailingDisplay:
    return _FailingDisplay()


@pytest.fixture
def failing_lux(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Replace LuxDisplay so show/browse hit the display_failed branch."""
    monkeypatch.setattr("punt_zspec.display.LuxDisplay", _make_failing_display)
    yield


# ---------------------------------------------------------------------------
# partition / audit — happy paths
# ---------------------------------------------------------------------------


def test_partition_reads_stdin_and_prints_saved_path(spec: Path) -> None:
    result = _RUNNER.invoke(app, ["partition", str(spec)], input=_VALID_PARTITION)

    assert result.exit_code == 0
    assert result.stdout.strip() == str(spec.parent / "s.partition.json")


def test_audit_reads_stdin_and_prints_saved_path(spec: Path) -> None:
    result = _RUNNER.invoke(app, ["audit", str(spec)], input=_VALID_AUDIT)

    assert result.exit_code == 0
    assert result.stdout.strip() == str(spec.parent / "s.audit.json")


def test_partition_reads_report_file(spec: Path, tmp_path: Path) -> None:
    report = tmp_path / "in.json"
    report.write_text(_VALID_PARTITION, encoding="utf-8")

    result = _RUNNER.invoke(app, ["partition", str(spec), "--report", str(report)])

    assert result.exit_code == 0
    assert result.stdout.strip() == str(spec.parent / "s.partition.json")


# ---------------------------------------------------------------------------
# _read_report — unreadable file paths
# ---------------------------------------------------------------------------


def test_partition_missing_report_file_is_clean_error(
    spec: Path, tmp_path: Path
) -> None:
    missing = tmp_path / "nope.json"

    result = _RUNNER.invoke(app, ["partition", str(spec), "--report", str(missing)])

    assert result.exit_code == 1
    assert "error: cannot read report:" in result.stderr
    assert "Traceback" not in result.stderr


def test_partition_non_utf8_report_file_is_clean_error(
    spec: Path, tmp_path: Path
) -> None:
    raw = tmp_path / "raw.json"
    raw.write_bytes(b"\xff\xfe")

    result = _RUNNER.invoke(app, ["partition", str(spec), "--report", str(raw)])

    assert result.exit_code == 1
    assert "error: cannot read report:" in result.stderr
    assert "Traceback" not in result.stderr


# ---------------------------------------------------------------------------
# partition / audit — invalid report bodies
# ---------------------------------------------------------------------------


def test_partition_invalid_json_is_clean_error(spec: Path) -> None:
    result = _RUNNER.invoke(app, ["partition", str(spec)], input="not json")

    assert result.exit_code == 1
    assert "error: Invalid partition report:" in result.stderr
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize("payload", ["[]", "null"])
def test_partition_non_dict_json_is_clean_error(spec: Path, payload: str) -> None:
    result = _RUNNER.invoke(app, ["partition", str(spec)], input=payload)

    assert result.exit_code == 1
    assert "error: Invalid partition report:" in result.stderr
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize("payload", ["[]", "null"])
def test_audit_non_dict_json_is_clean_error(spec: Path, payload: str) -> None:
    result = _RUNNER.invoke(app, ["audit", str(spec)], input=payload)

    assert result.exit_code == 1
    assert "error: Invalid audit report:" in result.stderr
    assert "Traceback" not in result.stderr


# ---------------------------------------------------------------------------
# show / browse — display error paths
# ---------------------------------------------------------------------------


def test_show_display_failure_is_clean_error(spec: Path, failing_lux: None) -> None:
    result = _RUNNER.invoke(app, ["show", str(spec)])

    assert result.exit_code == 1
    assert "error:" in result.stderr
    assert "Traceback" not in result.stderr


def test_browse_invalid_manifest_is_clean_error(
    tmp_path: Path, failing_lux: None
) -> None:
    manifest = tmp_path / "manifest.toml"
    manifest.write_text("this is not valid toml {", encoding="utf-8")

    result = _RUNNER.invoke(app, ["browse", str(manifest)])

    assert result.exit_code == 1
    assert "error:" in result.stderr
    assert "Traceback" not in result.stderr


# ---------------------------------------------------------------------------
# enable / disable
# ---------------------------------------------------------------------------


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Return a bare repository root with a user-owned CLAUDE.md."""
    (tmp_path / ".git").mkdir()
    (tmp_path / "CLAUDE.md").write_text("# Project\n", encoding="utf-8")
    return tmp_path


def test_enable_prints_the_three_paths_and_the_commit_reminder(repo: Path) -> None:
    result = _RUNNER.invoke(app, ["enable", str(repo)])

    assert result.exit_code == 0
    assert "z-spec enabled in" in result.stdout
    assert "@.punt-labs/z-spec/CLAUDE.md" in result.stdout
    assert "Commit the marker" in result.stdout
    assert (repo / ".punt-labs" / "z-spec" / "enabled").is_file()


def test_enable_is_idempotent_from_the_cli(repo: Path) -> None:
    _RUNNER.invoke(app, ["enable", str(repo)])
    result = _RUNNER.invoke(app, ["enable", str(repo)])

    assert result.exit_code == 0
    assert (repo / "CLAUDE.md").read_text().count("@.punt-labs/z-spec/CLAUDE.md") == 1


def test_disable_reports_the_off_state(repo: Path) -> None:
    _RUNNER.invoke(app, ["enable", str(repo)])

    result = _RUNNER.invoke(app, ["disable", str(repo)])

    assert result.exit_code == 0
    assert "z-spec disabled in" in result.stdout
    assert not (repo / ".punt-labs" / "z-spec" / "enabled").exists()
    assert (repo / ".punt-labs" / "z-spec" / "CLAUDE.md").is_file()


def test_enable_on_a_repo_that_refuses_the_write_is_a_clean_error(repo: Path) -> None:
    # `.punt-labs` as a regular file is the cheapest way to make every write
    # enable performs fail. The CLI must print the failure, not a traceback.
    (repo / ".punt-labs").write_text("not a directory\n", encoding="utf-8")

    result = _RUNNER.invoke(app, ["enable", str(repo)])

    assert result.exit_code == 1
    assert "error: Failed to enable z-spec" in result.stderr
    assert "Traceback" not in result.stderr


def test_enable_outside_a_repository_is_a_clean_error(tmp_path: Path) -> None:
    result = _RUNNER.invoke(app, ["enable", tmp_path.anchor])

    assert result.exit_code == 1
    assert "error: not inside a git repository" in result.stderr
    assert "Traceback" not in result.stderr
