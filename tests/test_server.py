"""Tests for punt_zspec.server."""

from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from punt_zspec.server import _lifespan, mcp  # pyright: ignore[reportPrivateUsage]


def test_server_has_correct_name() -> None:
    assert mcp.name == "zspec"


def test_server_has_all_tools() -> None:
    tool_names = {tool.name for tool in mcp._tool_manager.list_tools()}  # pyright: ignore[reportPrivateUsage]
    expected = {
        "check",
        "test",
        "animate",
        "model_check",
        "show_z_spec",
        "get_report",
        "save_partition_report",
        "save_audit_report",
        "browse",
    }
    assert expected == tool_names


# ---------------------------------------------------------------------------
# Lifespan (eager Lux connect)
# ---------------------------------------------------------------------------


def _run_lifespan() -> None:
    """Helper: enter and exit the lifespan context manager."""

    async def _go() -> None:
        async with _lifespan(MagicMock()):
            pass

    asyncio.run(_go())


def test_lifespan_success() -> None:
    """Lifespan calls _eager_lux_connect (-> _get_client) to eagerly connect."""
    with patch("punt_zspec.server._get_client") as mock:
        _run_lifespan()
    mock.assert_called_once()


def test_lifespan_connection_error() -> None:
    """ConnectionError is caught at debug — server still starts."""
    with patch(
        "punt_zspec.server._get_client",
        side_effect=ConnectionError("refused"),
    ):
        _run_lifespan()  # should not raise


def test_lifespan_os_error() -> None:
    """OSError is caught at debug — server still starts."""
    with patch(
        "punt_zspec.server._get_client",
        side_effect=OSError("socket gone"),
    ):
        _run_lifespan()  # should not raise


def test_lifespan_import_error() -> None:
    """ImportError is caught at warning — server still starts."""
    with patch(
        "punt_zspec.server._get_client",
        side_effect=ImportError("No module named 'punt_lux'"),
    ):
        _run_lifespan()  # should not raise


def test_lifespan_unexpected_error() -> None:
    """Unexpected exceptions are caught at warning — server still starts."""
    with patch(
        "punt_zspec.server._get_client",
        side_effect=TypeError("bad arg"),
    ):
        _run_lifespan()  # should not raise


# ---------------------------------------------------------------------------
# check tool
# ---------------------------------------------------------------------------


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
    # Fuzz result should be saved
    assert (tmp_path / "spec.fuzz.json").exists()


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


def test_show_z_spec_file_not_found() -> None:
    from punt_zspec.server import show_z_spec

    result = json.loads(show_z_spec("nonexistent.tex"))
    assert result["status"] == "error"
    assert "Spec file not found" in result["error"]


def test_show_z_spec_displayed(tmp_path: Path) -> None:
    """show_z_spec with mocked LuxClient returns displayed status."""
    from punt_zspec.server import show_z_spec

    tex = tmp_path / "spec.tex"
    tex.write_text(
        r"""\documentclass{article}
\begin{document}
\section{State}
\begin{schema}{Foo}
x : \nat
\where
x \leq 10
\end{schema}
\end{document}
"""
    )
    mock_client = MagicMock()
    with patch("punt_zspec.server._get_client", return_value=mock_client):
        result = json.loads(show_z_spec(str(tex)))
    assert result["status"] == "displayed"
    assert result["scene_id"] == "z-spec"


def test_show_z_spec_lux_error(tmp_path: Path) -> None:
    """show_z_spec returns error status when lux is unavailable."""
    from punt_zspec.server import show_z_spec

    tex = tmp_path / "spec.tex"
    tex.write_text(
        r"""\documentclass{article}
\begin{document}
\section{State}
\begin{schema}{Foo}
x : \nat
\end{schema}
\end{document}
"""
    )
    with patch(
        "punt_zspec.server._get_client",
        side_effect=ConnectionError("lux not running"),
    ):
        result = json.loads(show_z_spec(str(tex)))
    assert result["status"] == "error"
    assert "lux not running" in result["message"]


# ---------------------------------------------------------------------------
# save_partition_report
# ---------------------------------------------------------------------------


def test_save_partition_report_success(tmp_path: Path) -> None:
    from punt_zspec.server import save_partition_report

    tex = tmp_path / "spec.tex"
    tex.write_text("dummy")
    report_json = json.dumps(
        {
            "specification": "spec.tex",
            "timestamp": "2026-03-12T00:00:00Z",
            "operations": [
                {
                    "name": "Increment",
                    "kind": "delta",
                    "inputs": [],
                    "stateVars": ["x"],
                    "branches": [],
                    "partitions": [
                        {
                            "id": 1,
                            "class": "happy-path",
                            "branch": 1,
                            "status": "accepted",
                            "inputs": {"n": 1},
                            "preState": {"x": 5},
                            "postState": {"x": 6},
                            "notes": "Normal",
                        }
                    ],
                }
            ],
        }
    )
    result = json.loads(save_partition_report(str(tex), report_json))
    assert result["ok"] is True
    assert (tmp_path / "spec.partition.json").exists()


def test_save_partition_report_invalid_json(tmp_path: Path) -> None:
    from punt_zspec.server import save_partition_report

    tex = tmp_path / "spec.tex"
    tex.write_text("dummy")
    result = json.loads(save_partition_report(str(tex), "not json"))
    assert result["ok"] is False
    assert "Invalid partition report" in result["error"]


# ---------------------------------------------------------------------------
# save_audit_report
# ---------------------------------------------------------------------------


def test_save_audit_report_success(tmp_path: Path) -> None:
    from punt_zspec.server import save_audit_report

    tex = tmp_path / "spec.tex"
    tex.write_text("dummy")
    report_json = json.dumps(
        {
            "specification": "spec.tex",
            "testDirectory": "tests/",
            "timestamp": "2026-03-12T00:00:00Z",
            "constraints": [
                {
                    "text": "x <= 10",
                    "category": "invariant",
                    "source": "State",
                    "coveredBy": "test_state.py:15",
                    "confidence": "high",
                }
            ],
            "uncovered": [
                {
                    "text": "x >= 0",
                    "category": "invariant",
                    "source": "State",
                    "suggestion": "Test lower bound",
                }
            ],
        }
    )
    result = json.loads(save_audit_report(str(tex), report_json))
    assert result["ok"] is True
    assert (tmp_path / "spec.audit.json").exists()


def test_save_audit_report_invalid_json(tmp_path: Path) -> None:
    from punt_zspec.server import save_audit_report

    tex = tmp_path / "spec.tex"
    tex.write_text("dummy")
    result = json.loads(save_audit_report(str(tex), "{bad}"))
    assert result["ok"] is False
    assert "Invalid audit report" in result["error"]


# ---------------------------------------------------------------------------
# browse
# ---------------------------------------------------------------------------


def test_browse_manifest_not_found() -> None:
    from punt_zspec.server import browse

    result = json.loads(browse("/nonexistent/manifest.toml"))
    assert result["status"] == "error"
    assert "not found" in result["error"].lower()


def test_browse_success(tmp_path: Path) -> None:
    from punt_zspec.server import browse

    manifest = tmp_path / "manifest.toml"
    manifest.write_text(
        """\
[collection]
title = "Test Collection"

[[lessons]]
title = "Lesson 1"
spec = "01.tex"
annotation = "Hello"
""",
        encoding="utf-8",
    )
    tex = tmp_path / "01.tex"
    tex.write_text(
        r"""\documentclass{article}
\begin{document}
\section{State}
\begin{schema}{Foo}
x : \nat
\end{schema}
\end{document}
"""
    )

    mock_client = MagicMock()
    with patch("punt_zspec.server._get_client", return_value=mock_client):
        result = json.loads(browse(str(manifest)))
    assert result["status"] == "displayed"
    assert result["total"] == 1
    assert result["title"] == "Test Collection"
