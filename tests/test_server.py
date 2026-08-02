"""Tests for punt_zspec.server."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

from punt_lux.rest_transport import HubUnavailableError

from punt_zspec.commands.enablement import RepoEnablement
from punt_zspec.gate import EnablementGate
from punt_zspec.lux import ZSpecLuxSession
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


def _enablement(action: str, directory: str, monkeypatch: pytest.MonkeyPatch) -> Any:
    """Run the enablement tool with the lux session stubbed out, and parse it.

    The tool syncs the menu to the marker it just wrote, and a test must not
    reach the developer's running luxd to do it — the sync itself is asserted
    separately, on the stub.
    """
    from punt_zspec.server import enablement

    session = MagicMock()
    session.sync = AsyncMock()
    monkeypatch.setattr("punt_zspec.server._SESSION", session)
    return json.loads(asyncio.run(enablement(action, directory)))


def test_enablement_tool_takes_a_verb_not_a_boolean(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # §2.14: the MCP surface takes action="enable"|"disable"; the retired
    # y|n vocabulary must not reappear as an enabled: bool parameter.
    result = _enablement("enable", str(_repo(tmp_path)), monkeypatch)

    assert result["ok"] is True
    assert result["action"] == "enable"
    assert result["enabled"] is True


def test_enablement_tool_writes_the_same_marker_as_the_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path)
    _enablement("enable", str(root), monkeypatch)

    assert (root / ".punt-labs" / "z-spec" / "enabled").is_file()
    assert "@.punt-labs/z-spec/CLAUDE.md" in (root / "CLAUDE.md").read_text()


def test_enablement_tool_disables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path)
    _enablement("enable", str(root), monkeypatch)

    result = _enablement("disable", str(root), monkeypatch)
    assert result["enabled"] is False
    assert not (root / ".punt-labs" / "z-spec" / "enabled").exists()


def test_enablement_tool_outside_a_repository_returns_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _enablement("enable", tmp_path.anchor, monkeypatch)

    assert result["ok"] is False
    assert "not inside a git repository" in result["error"]


def test_enablement_tool_syncs_the_menu_to_the_marker_it_wrote(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Both verbs must move the menu now, not at the next server reconnect.

    The tools re-read the marker per call, so `enable` opens them immediately;
    without this the Tutorial and Browse entries would lag behind — absent after
    an enable, and still clickable after a disable.
    """
    from punt_zspec.server import enablement

    session = MagicMock()
    session.sync = AsyncMock()
    monkeypatch.setattr("punt_zspec.server._SESSION", session)

    asyncio.run(enablement("enable", str(_repo(tmp_path))))

    session.sync.assert_awaited_once()


# ---------------------------------------------------------------------------
# the gate — the MCP surface answers only where the marker is present
# ---------------------------------------------------------------------------


def _bare_repo(root: Path) -> Path:
    """Return a repo root with no marker: z-spec is not enabled there."""
    root.mkdir(parents=True, exist_ok=True)
    (root / ".git").mkdir()
    (root / "CLAUDE.md").write_text("# Project\n", encoding="utf-8")
    return root


def _enabled_repo(root: Path) -> Path:
    """Return a repo root carrying the marker, as every plugin checkout does."""
    RepoEnablement.for_repo(_bare_repo(root)).enable()
    return root


# The probe program. ``_SESSION`` is replaced before the call: these tests
# assert on where the gate and the tool defaults point, and a probe that let
# the enablement tool sync for real would reach the developer's running luxd
# and register menu entries from a throwaway subprocess.
_PROBE = '''\
import asyncio
import punt_zspec.server as s


class _NoMenu:
    """A lux session stand-in with nothing behind it."""

    async def sync(self):
        pass

    async def stop(self):
        pass


s._SESSION = _NoMenu()
print({call})
'''


def _launched_as_the_plugin(project: Path, checkout: Path, call: str) -> Any:
    """Evaluate ``call`` in a process started the way plugin.json does.

    ``uv run --directory ${CLAUDE_PLUGIN_ROOT}`` chdirs before exec, so the
    server's cwd is the plugin checkout and only ``CLAUDE_PROJECT_DIR`` names
    the user's repo. A subprocess is the only honest way to stage that: the
    gate and the tool defaults are wired at import, and what these tests exist
    to prove is that they are wired to the project and not to the cwd.
    """
    env = {
        **os.environ,
        "CLAUDE_PROJECT_DIR": str(project),
        "ZSPEC_PLUGIN_ROOT": str(checkout),
    }
    proc = subprocess.run(
        [sys.executable, "-c", _PROBE.format(call=call)],
        cwd=checkout,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


async def _drive_lifespan() -> None:
    from punt_zspec.server import lifespan

    async with lifespan(mcp):
        pass


def test_a_gated_tool_declines_where_the_project_has_no_marker(
    tmp_path: Path,
) -> None:
    # The shipped plugin checkout carries z-spec's own committed marker (§2.7),
    # so a gate reading the cwd reads permanently open — a no-op for every user.
    checkout = _enabled_repo(tmp_path / "plugin")
    project = _bare_repo(tmp_path / "project")

    result = _launched_as_the_plugin(project, checkout, 's.check("spec.tex")')

    assert result["ok"] is False
    assert "z-spec enable" in result["error"]
    # §2.3 no auto-enable: declining never turns z-spec on.
    assert not (project / ".punt-labs").exists()


def test_a_gated_tool_answers_on_the_project_s_own_marker(tmp_path: Path) -> None:
    checkout = _bare_repo(tmp_path / "plugin")
    project = _enabled_repo(tmp_path / "project")

    result = _launched_as_the_plugin(project, checkout, 's.check("spec.tex")')

    assert result["ok"] is False
    assert "Spec file not found" in result["error"]


def test_the_enablement_tool_defaults_to_the_project_not_the_checkout(
    tmp_path: Path,
) -> None:
    # Also the proof that the door is not behind the lock it opens: the project
    # has no marker, so the gate is shut, and the tool still answers.
    checkout = _bare_repo(tmp_path / "plugin")
    project = _bare_repo(tmp_path / "project")

    result = _launched_as_the_plugin(
        project, checkout, 'asyncio.run(s.enablement("enable"))'
    )

    assert result["ok"] is True
    assert (project / ".punt-labs" / "z-spec" / "enabled").is_file()
    assert not (checkout / ".punt-labs").exists()
    assert (checkout / "CLAUDE.md").read_text(encoding="utf-8") == "# Project\n"


def test_the_lifespan_syncs_the_menu_to_the_marker_and_drains_on_shutdown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The lifespan asks; the session decides.

    Gating the lifespan itself is what made the menu a startup snapshot: it
    could only ever answer the marker as it stood the moment the server
    connected. The decision belongs where it can be re-taken — in the session,
    which the enablement tool also drives.
    """
    session = MagicMock()
    session.sync = AsyncMock()
    session.stop = AsyncMock()
    monkeypatch.setattr("punt_zspec.server._SESSION", session)

    asyncio.run(_drive_lifespan())

    session.sync.assert_awaited_once()
    session.stop.assert_awaited_once()


def test_the_menu_follows_the_project_marker_without_a_reconnect(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """End to end over the real gate: enable brings the receive leg up at once.

    This is what `/z-spec:enable` does in a repo the server started in with no
    marker. Gated once in the lifespan, the listener never started and the
    Tutorial and Browse entries stayed absent until the server reconnected,
    while every tool had already opened.
    """
    monkeypatch.setattr(
        "punt_zspec.lux.clients.LuxRestClient.for_identity",
        MagicMock(side_effect=HubUnavailableError("luxd not running")),
    )
    project = _bare_repo(tmp_path / "project")
    session = ZSpecLuxSession(EnablementGate(project).is_open, cwd=project)

    async def scenario() -> tuple[bool, bool]:
        await session.sync()
        was_off = session._task is None  # pyright: ignore[reportPrivateUsage]
        RepoEnablement.for_repo(project).enable()
        await session.sync()
        is_on = session._task is not None  # pyright: ignore[reportPrivateUsage]
        await session.stop()
        return was_off, is_on

    assert asyncio.run(scenario()) == (True, True)
