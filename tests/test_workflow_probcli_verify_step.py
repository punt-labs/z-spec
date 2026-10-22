"""The specs job's verify step, run offline: probcli and fuzz must resolve.

Each test runs the shipped ``run:`` block through ``workflow_step_runner``
under ``bash -e`` with a stub ``probcli`` (and ``fuzz``) first on PATH, so
the step's exact-version check and its diagnostics can be driven directly.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.workflow_step_runner import PROB_VERSION, StepHarness


@pytest.mark.parametrize(
    "body",
    [
        f"echo 'ProB command line, version {PROB_VERSION}'",
        f"echo 'ProB command line, version {PROB_VERSION}' >&2",
        f"echo 'ProB {PROB_VERSION}'; echo 'built with Tcl 8.6.13, SICStus 4.9.0'",
    ],
    ids=["stdout", "stderr-only", "first-version-wins"],
)
def test_verify_accepts_the_pinned_version(tmp_path: Path, body: str) -> None:
    result = StepHarness.verify(body).run(tmp_path).result
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    ("body", "got"),
    [
        (f"echo 'ProB {PROB_VERSION}0'", f"{PROB_VERSION}0"),
        ("echo 'ProB, no version'", "unreadable"),
    ],
)
def test_verify_rejects_any_other_version(tmp_path: Path, body: str, got: str) -> None:
    result = StepHarness.verify(body).run(tmp_path).result
    assert result.returncode != 0
    assert f"FATAL: expected probcli {PROB_VERSION}, got: {got}" in result.stderr


def test_verify_shows_why_probcli_would_not_run(tmp_path: Path) -> None:
    body = "echo 'error while loading shared libraries: libtcl8.6.so' >&2; exit 127"
    result = StepHarness.verify(body).run(tmp_path).result
    assert result.returncode != 0
    assert "-version failed; its output:" in result.stderr
    assert "libtcl8.6.so" in result.stderr


def test_verify_names_a_missing_fuzz(tmp_path: Path) -> None:
    # PATH is the stub directory alone: a host fuzz cannot satisfy the step.
    result = StepHarness.verify(f"echo {PROB_VERSION}", fuzz=False).run(tmp_path).result
    assert result.returncode != 0
    assert "FATAL: fuzz is not on PATH" in result.stderr
