"""Tests for punt_zspec.server."""

from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

from punt_lux.rest_transport import HubUnavailableError

from punt_zspec.server import mcp

if TYPE_CHECKING:
    import pytest


def test_server_has_correct_name() -> None:
    assert mcp.name == "zspec"


# The full MCP tool set and its CLI counterpart are enforced by the
# registry-driven parity guard in tests/commands/test_parity.py.


# ---------------------------------------------------------------------------
# check tool
# ---------------------------------------------------------------------------


def test_check_tool_file_not_found() -> None:
    from punt_zspec.server import check

    result = json.loads(check("nonexistent.tex"))
    assert result["ok"] is False
    assert "Spec file not found" in result["error"]


def test_check_tool_fuzz_not_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tex = tmp_path / "spec.tex"
    tex.write_text("dummy")
    # Make resolve_fuzz genuinely fail: $FUZZ points nowhere and PATH is empty.
    monkeypatch.setenv("FUZZ", str(tmp_path / "no-such-fuzz"))
    monkeypatch.setenv("PATH", "")
    from punt_zspec.server import check

    result = json.loads(check(str(tex)))
    assert result["ok"] is False
    assert "fuzz not found" in result["error"]


def test_check_tool_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tex = tmp_path / "spec.tex"
    tex.write_text("dummy")
    # $FUZZ points at a real file so resolve_fuzz returns it; the run itself
    # is stubbed to a clean exit so the test needs no installed fuzz.
    fake_fuzz = tmp_path / "fuzz"
    fake_fuzz.write_text("")
    monkeypatch.setenv("FUZZ", str(fake_fuzz))

    mock_result = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="0 type errors\n", stderr=""
    )
    with patch("subprocess.run", return_value=mock_result):
        from punt_zspec.server import check

        result = json.loads(check(str(tex)))
    assert result["ok"] is True
    # Fuzz result should be saved
    assert (tmp_path / "spec.fuzz.json").exists()


def test_doctor_tool_returns_health() -> None:
    from punt_zspec.server import doctor

    result = json.loads(doctor())
    assert "version" in result
    assert "healthy" in result
    assert isinstance(result["healthy"], bool)


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
    assert result["ok"] is False
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
    with patch(
        "punt_zspec.lux.clients.LuxRestClient.for_identity", return_value=mock_client
    ):
        result = json.loads(show_z_spec(str(tex)))
    assert result["ok"] is True
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
        "punt_zspec.lux.clients.LuxRestClient.for_identity",
        side_effect=HubUnavailableError("lux not running"),
    ):
        result = json.loads(show_z_spec(str(tex)))
    assert result["ok"] is False
    assert "lux not running" in result["error"]


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
    assert result["ok"] is False
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
    with patch(
        "punt_zspec.lux.clients.LuxRestClient.for_identity", return_value=mock_client
    ):
        result = json.loads(browse(str(manifest)))
    assert result["ok"] is True
    assert result["total"] == 1
    assert result["title"] == "Test Collection"


# ---------------------------------------------------------------------------
# enablement tool
# ---------------------------------------------------------------------------


def _repo(tmp_path: Path) -> Path:
    (tmp_path / ".git").mkdir()
    (tmp_path / "CLAUDE.md").write_text("# Project\n", encoding="utf-8")
    return tmp_path


def test_enablement_tool_takes_a_verb_not_a_boolean(tmp_path: Path) -> None:
    # §2.14: the MCP surface takes action="enable"|"disable"; the retired
    # y|n vocabulary must not reappear as an enabled: bool parameter.
    from punt_zspec.server import enablement

    result = json.loads(enablement("enable", str(_repo(tmp_path))))
    assert result["ok"] is True
    assert result["action"] == "enable"
    assert result["enabled"] is True


def test_enablement_tool_writes_the_same_marker_as_the_cli(tmp_path: Path) -> None:
    from punt_zspec.server import enablement

    root = _repo(tmp_path)
    enablement("enable", str(root))

    assert (root / ".punt-labs" / "z-spec" / "enabled").is_file()
    assert "@.punt-labs/z-spec/CLAUDE.md" in (root / "CLAUDE.md").read_text()


def test_enablement_tool_disables(tmp_path: Path) -> None:
    from punt_zspec.server import enablement

    root = _repo(tmp_path)
    enablement("enable", str(root))

    result = json.loads(enablement("disable", str(root)))
    assert result["enabled"] is False
    assert not (root / ".punt-labs" / "z-spec" / "enabled").exists()


def test_enablement_tool_outside_a_repository_returns_an_error(tmp_path: Path) -> None:
    from punt_zspec.server import enablement

    result = json.loads(enablement("enable", tmp_path.anchor))
    assert result["ok"] is False
    assert "not inside a git repository" in result["error"]


# ---------------------------------------------------------------------------
# the gate — the MCP surface answers only where the marker is present
# ---------------------------------------------------------------------------


def _bare_repo(tmp_path: Path) -> Path:
    """Return a repo root with no marker: z-spec is not enabled there."""
    (tmp_path / ".git").mkdir()
    (tmp_path / "CLAUDE.md").write_text("# Project\n", encoding="utf-8")
    return tmp_path


async def _drive_lifespan() -> None:
    from punt_zspec.server import lifespan

    async with lifespan(mcp):
        pass


def test_a_gated_tool_declines_where_the_marker_is_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from punt_zspec.server import check

    monkeypatch.chdir(_bare_repo(tmp_path))

    result = json.loads(check("spec.tex"))
    assert result["ok"] is False
    assert "z-spec enable" in result["error"]


def test_declining_does_not_write_the_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # §2.3 no auto-enable: first use never turns z-spec on.
    from punt_zspec.server import doctor

    root = _bare_repo(tmp_path)
    monkeypatch.chdir(root)

    doctor()
    assert not (root / ".punt-labs").exists()


def test_a_gated_tool_answers_once_the_marker_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from punt_zspec.server import check, enablement

    monkeypatch.chdir(_bare_repo(tmp_path))
    enablement("enable")

    result = json.loads(check("spec.tex"))
    assert result["ok"] is False
    assert "Spec file not found" in result["error"]


def test_the_enablement_tool_is_not_gated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The door cannot be behind the lock it opens.
    from punt_zspec.server import enablement

    root = _bare_repo(tmp_path)
    monkeypatch.chdir(root)

    result = json.loads(enablement("enable"))
    assert result["ok"] is True
    assert (root / ".punt-labs" / "z-spec" / "enabled").is_file()


def test_the_lifespan_registers_no_menu_where_the_marker_is_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(_bare_repo(tmp_path))
    session = MagicMock()
    session.start = AsyncMock()
    session.stop = AsyncMock()
    monkeypatch.setattr("punt_zspec.server._SESSION", session)

    asyncio.run(_drive_lifespan())

    session.start.assert_not_called()
    session.stop.assert_not_called()


def test_the_lifespan_registers_the_menu_where_the_marker_is_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from punt_zspec.server import enablement

    monkeypatch.chdir(_bare_repo(tmp_path))
    enablement("enable")
    session = MagicMock()
    session.start = AsyncMock()
    session.stop = AsyncMock()
    monkeypatch.setattr("punt_zspec.server._SESSION", session)

    asyncio.run(_drive_lifespan())

    session.start.assert_awaited_once()
    session.stop.assert_awaited_once()
