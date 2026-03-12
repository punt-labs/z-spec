"""Tests for punt_zspec.server."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

from punt_zspec.server import mcp


def test_server_has_correct_name() -> None:
    assert mcp.name == "grimoire"


def test_server_has_all_tools() -> None:
    tool_names = {tool.name for tool in mcp._tool_manager.list_tools()}  # pyright: ignore[reportPrivateUsage]
    expected = {"check", "test", "animate", "model_check", "show_z_spec", "get_report"}
    assert expected == tool_names


def test_check_tool_file_not_found() -> None:
    from punt_zspec.server import check

    result = json.loads(check("nonexistent.tex"))
    assert result["ok"] is False
    assert "Spec file not found" in result["error"]


def test_check_tool_fuzz_not_found(tmp_path: Path) -> None:
    tex = tmp_path / "spec.tex"
    tex.write_text("dummy")
    with patch("punt_zspec.fuzz.resolve_fuzz", return_value=None):
        from punt_zspec.server import check

        result = json.loads(check(str(tex)))
    assert result["ok"] is False
    assert "fuzz not found" in result["error"]


def test_check_tool_success(tmp_path: Path) -> None:
    tex = tmp_path / "spec.tex"
    tex.write_text("dummy")

    mock_result = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="0 type errors\n", stderr=""
    )
    with (
        patch("punt_zspec.fuzz.resolve_fuzz", return_value=Path("/usr/bin/fuzz")),
        patch("subprocess.run", return_value=mock_result),
    ):
        from punt_zspec.server import check

        result = json.loads(check(str(tex)))
    assert result["ok"] is True


def test_get_report_missing() -> None:
    from punt_zspec.server import get_report

    result = json.loads(get_report("/nonexistent/path.tex"))
    assert result["ok"] is False
    assert "No report" in result["error"]


def test_get_report_found(tmp_path: Path) -> None:
    from punt_zspec.report import save_report
    from punt_zspec.types import CheckResult, CheckStatus, ProbReport

    tex = tmp_path / "spec.tex"
    tex.write_text("dummy")
    report = ProbReport(
        timestamp="2026-03-12T00:00:00Z",
        probcli_version="1.13.1",
        setsize=2,
        checks=[CheckResult(name="init", status=CheckStatus.passed)],
        operations=[],
        counter_example=None,
        states_analysed=10,
        transitions_fired=20,
    )
    save_report(tex, report)

    from punt_zspec.server import get_report

    result = json.loads(get_report(str(tex)))
    assert result["ok"] is True
    assert result["states_analysed"] == 10
