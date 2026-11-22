"""Run the report-only design step with successful, empty and failing reports."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from tests.workflow_source import Workflow

_ROOT = Path(__file__).resolve().parent.parent
_WORKFLOW = _ROOT / ".github/workflows/lint.yml"
_STEP = "Design ratchet (shadow, report only)"


def test_design_shadow_is_a_pr_report_not_a_gate() -> None:
    workflow = Workflow(_WORKFLOW)
    index, step = workflow.step("lint", _STEP)
    ratchet_index, _ = workflow.step("lint", "Ratchets (PR")
    assert index > ratchet_index
    assert step.field("if") == (
        "${{ !cancelled() && github.event_name == 'pull_request' }}"
    )
    assert step.field("continue-on-error") == "true"
    assert step.field("DESIGN_BASE") == "origin/${{ github.base_ref }}"
    assert "${{" not in "\n".join(step.script())
    check = next(
        line
        for line in (_ROOT / "Makefile").read_text().splitlines()
        if line.startswith("check:")
    )
    assert "design-shadow" not in check


@pytest.mark.parametrize(
    ("status", "output"),
    [(0, "neutral\n"), (0, ""), (2, "FAIL: invalid reference\n")],
)
def test_design_shadow_publishes_even_failed_reports(
    tmp_path: Path, status: int, output: str
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
    env = {
        **os.environ,
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "GITHUB_STEP_SUMMARY": str(summary),
        "DESIGN_BASE": "origin/other-base",
        "ARGV_LOG": str(argv_log),
        "SHADOW_OUTPUT": output,
        "SHADOW_STATUS": str(status),
    }
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
    assert result.returncode == 0, result.stderr
    assert argv_log.read_text().strip() == (
        "run oo-ratchet design src/punt_zspec --shadow-check origin/other-base"
    )
    report = summary.read_text()
    assert report.startswith("Earlier step\n### Design ratchet (shadow, report only)")
    assert report == "Earlier step\n" + result.stdout
    assert report.endswith("```\n")
    assert output in report
    assert output in result.stdout
