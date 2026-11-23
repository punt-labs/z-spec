"""Exercise the PR design gate and its summary for passing and failing reports."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from tests.workflow_source import Workflow

_ROOT = Path(__file__).resolve().parent.parent
_WORKFLOW = _ROOT / ".github/workflows/lint.yml"
_STEP = "Design ratchet (gate)"


def _make_isolated_env(**overrides: str) -> dict[str, str]:
    """Return the environment without recursive-make control variables."""
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"MAKEFLAGS", "MFLAGS", "MAKELEVEL"}
    }
    env.update(overrides)
    return env


def test_design_gate_step_is_pr_only_and_check_includes_it() -> None:
    workflow = Workflow(_WORKFLOW)
    index, step = workflow.step("lint", _STEP)
    ratchet_index, _ = workflow.step("lint", "Ratchets (PR")
    assert index > ratchet_index
    assert step.field("if") == (
        "${{ !cancelled() && github.event_name == 'pull_request' }}"
    )
    assert not step.has("continue-on-error")
    assert step.field("DESIGN_BASE") == "origin/${{ github.base_ref }}"
    assert "${{" not in "\n".join(step.script())
    check = next(
        line
        for line in (_ROOT / "Makefile").read_text().splitlines()
        if line.startswith("check:")
    )
    assert "design-gate" in check


def test_make_isolated_env_drops_recursive_make_controls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MAKEFLAGS", "DESIGN_BASE=HEAD~1")
    monkeypatch.setenv("MFLAGS", "DESIGN_BASE=HEAD~1")
    monkeypatch.setenv("MAKELEVEL", "1")
    monkeypatch.setenv("Z_SPEC_TEST_SENTINEL", "kept")

    env = _make_isolated_env(DESIGN_BASE="HEAD")

    assert "MAKEFLAGS" not in env
    assert "MFLAGS" not in env
    assert "MAKELEVEL" not in env
    assert env["DESIGN_BASE"] == "HEAD"
    assert env["Z_SPEC_TEST_SENTINEL"] == "kept"


def test_design_gate_missing_base_fails_before_scan(tmp_path: Path) -> None:
    invoked = tmp_path / "uv-invoked"
    uv = tmp_path / "uv"
    uv.write_text('#!/bin/sh\ntouch "$UV_INVOKED"\nexit 99\n')
    uv.chmod(0o755)
    missing = "origin/no-such-design-gate-base-z-spec"
    result = subprocess.run(
        ["make", "design-gate", f"DESIGN_BASE={missing}"],
        cwd=_ROOT,
        env=_make_isolated_env(
            PATH=f"{tmp_path}:{os.environ['PATH']}",
            UV_INVOKED=str(invoked),
        ),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert (
        f"FATAL: design-gate base ref '{missing}' does not resolve to a commit"
        in result.stderr
    )
    assert "fetch the base branch or set DESIGN_BASE" in result.stderr
    assert not invoked.exists()


@pytest.mark.parametrize(
    ("status", "output", "passes"),
    [
        (0, '{"verdict": "neutral"}\n', True),
        (0, '{"verdict": "good-deed"}\n', True),
        (0, '{"verdict": "good-deed: trade"}\n', True),
        (0, '{"verdict": "would-fail: tier0"}\n', False),
        (0, '{"verdict": "would-fail: tier1"}\n', False),
        (0, '{"verdict": "would-fail: tier2"}\n', False),
        (0, '{"verdict": "unknown"}\n', False),
        (0, "{}\n", False),
        (0, "[]\n", False),
        (0, "", False),
        (0, "invalid JSON\n", False),
        (2, "FAIL: invalid reference\n", False),
        (2, '{"verdict": "neutral"}\n', False),
    ],
)
def test_design_gate_publishes_and_preserves_failure(
    tmp_path: Path, status: int, output: str, passes: bool
) -> None:
    uv = tmp_path / "uv"
    uv.write_text(
        '#!/bin/sh\nprintf "%s\\n" "$*" > "$ARGV_LOG"\n'
        'printf "%s" "$SHADOW_OUTPUT"\nexit "$SHADOW_STATUS"\n'
    )
    uv.chmod(0o755)
    summary = tmp_path / "summary.md"
    summary.write_text("Earlier step\n")
    argv_log = tmp_path / "argv.txt"
    env = _make_isolated_env(
        PATH=f"{tmp_path}:{os.environ['PATH']}",
        GITHUB_STEP_SUMMARY=str(summary),
        DESIGN_BASE="HEAD",
        ARGV_LOG=str(argv_log),
        SHADOW_OUTPUT=output,
        SHADOW_STATUS=str(status),
    )
    _, step = Workflow(_WORKFLOW).step("lint", _STEP)
    result = subprocess.run(
        [
            "bash",
            "--noprofile",
            "--norc",
            "-e",
            "-o",
            "pipefail",
            "-c",
            "\n".join(step.script()),
        ],
        cwd=_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert (result.returncode == 0) is passes, result.stdout + result.stderr
    assert argv_log.read_text().strip() == (
        "run oo-ratchet design src/punt_zspec --shadow-check HEAD --json"
    )
    report = summary.read_text()
    assert report.startswith("Earlier step\n### Design ratchet (gate)")
    assert report == "Earlier step\n" + result.stdout
    assert report.endswith("```\n")
    assert output in report
    assert output in result.stdout
