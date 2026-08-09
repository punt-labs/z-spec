"""Tests for punt_zspec.prob.

The probcli output these tests feed the wrapper is captured from real runs
(``tests/fixtures/probcli``), never written by hand. What is mocked is the
process boundary — ``subprocess.run`` — so the argument list each run sends is
itself under test: a report that carries coverage must come from a run that
asked for it.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import patch

from punt_zspec.prob import (
    resolve_probcli,
    run_animate,
    run_full_suite,
    run_init,
    run_model_check,
)
from punt_zspec.types import CheckStatus

_FIXTURES = Path(__file__).parent / "fixtures" / "probcli"


def _transcript(name: str) -> str:
    return (_FIXTURES / name).read_text(encoding="utf-8")


_INIT = _transcript("init.out")
_ANIMATE = _transcript("animate.out")
_MODEL_CHECK_COVERED = _transcript("model-check-covered.out")
_MODEL_CHECK_UNCOVERED = _transcript("model-check-uncovered.out")
_MODEL_CHECK_COUNTER_EXAMPLE = _transcript("model-check-counter-example.out")
_CBC_ASSERTIONS = _transcript("cbc-assertions.out")
_CBC_DEADLOCK = _transcript("cbc-deadlock.out")

_BINARY = Path("/usr/bin/probcli")


def _spec(tmp_path: Path) -> Path:
    tex = tmp_path / "spec.tex"
    tex.write_text("dummy")
    return tex


def _mock_run(
    outputs: dict[str, str], returncode: int = 0
) -> Callable[..., subprocess.CompletedProcess[str]]:
    """Return a subprocess.run stand-in keyed on the probcli flag in the argv."""

    def mock(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        cmd = args[0] if args else kwargs.get("args", [])
        cmd_str = " ".join(str(c) for c in cmd)
        for key, output in outputs.items():
            if key in cmd_str:
                return subprocess.CompletedProcess(
                    args=cmd, returncode=returncode, stdout=output, stderr=""
                )
        return subprocess.CompletedProcess(
            args=cmd, returncode=0, stdout="OK\n", stderr=""
        )

    return mock


def _recorded_argv(calls: list[Any]) -> list[list[str]]:
    return [[str(part) for part in call.args[0]] for call in calls]


# ---------------------------------------------------------------------------
# Binary resolution
# ---------------------------------------------------------------------------


def test_resolve_probcli_from_env(tmp_path: Path) -> None:
    binary = tmp_path / "probcli"
    binary.write_text("#!/bin/sh\n")
    with patch.dict("os.environ", {"PROBCLI": str(binary)}):
        result = resolve_probcli()
    assert result == binary


def test_resolve_probcli_not_found() -> None:
    with (
        patch.dict("os.environ", {}, clear=True),
        patch("shutil.which", return_value=None),
        patch("pathlib.Path.is_file", return_value=False),
    ):
        result = resolve_probcli()
    assert result is None


# ---------------------------------------------------------------------------
# Every coverage-bearing run asks probcli for a census
# ---------------------------------------------------------------------------


def test_model_check_passes_the_coverage_flag(tmp_path: Path) -> None:
    mock = _mock_run({"-init": _INIT, "-model_check": _MODEL_CHECK_COVERED})
    with patch("subprocess.run", side_effect=mock) as run:
        run_model_check(_spec(tmp_path), _BINARY)

    model_check_argv = [
        a for a in _recorded_argv(run.call_args_list) if "-model_check" in a
    ]
    assert model_check_argv, "no model_check run was issued"
    assert all("-coverage" in argv for argv in model_check_argv)


def test_animate_passes_the_coverage_flag(tmp_path: Path) -> None:
    mock = _mock_run({"-init": _INIT, "-animate": _ANIMATE})
    with patch("subprocess.run", side_effect=mock) as run:
        run_animate(_spec(tmp_path), _BINARY)

    animate_argv = [a for a in _recorded_argv(run.call_args_list) if "-animate" in a]
    assert animate_argv
    assert all("-coverage" in argv for argv in animate_argv)


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------


def test_an_overrunning_run_is_reported_not_raised(tmp_path: Path) -> None:
    """An over-running model check must not reach the user as a traceback."""
    expired = subprocess.TimeoutExpired(cmd=["probcli"], timeout=330)
    with patch("subprocess.run", side_effect=expired):
        report = run_model_check(_spec(tmp_path), _BINARY)

    named = {c.name: c for c in report.checks}
    assert named["model_check"].status == CheckStatus.failed
    assert "exceeded" in named["model_check"].detail
    # The census is missing because the run died, not because -coverage was
    # omitted; the coverage line states what it observed and nothing more.
    assert named["coverage"].detail == "probcli printed no coverage census"
    assert not report.ok


def test_run_init_returns_the_run_output(tmp_path: Path) -> None:
    completed = subprocess.CompletedProcess(
        args=[], returncode=0, stdout=_INIT, stderr=""
    )
    with patch("subprocess.run", return_value=completed):
        output = run_init(_spec(tmp_path), _BINARY)

    assert output.check("init").status == CheckStatus.passed
    assert "EnterQuery" in output.declared_operations


# ---------------------------------------------------------------------------
# animate
# ---------------------------------------------------------------------------


def test_run_animate_reports_the_census_it_was_given(tmp_path: Path) -> None:
    mock = _mock_run({"-init": _INIT, "-animate": _ANIMATE})
    with patch("subprocess.run", side_effect=mock):
        report = run_animate(_spec(tmp_path), _BINARY)

    counts = {op.name: op.times_fired for op in report.operations}
    assert counts["ChangeCollection"] == 6
    assert counts["ClearHighlight"] == 0
    assert not report.ok  # ClearHighlight never fired


# ---------------------------------------------------------------------------
# model_check
# ---------------------------------------------------------------------------


def test_run_model_check_pass(tmp_path: Path) -> None:
    mock = _mock_run({"-init": _INIT, "-model_check": _MODEL_CHECK_COVERED})
    with patch("subprocess.run", side_effect=mock):
        report = run_model_check(_spec(tmp_path), _BINARY)

    assert report.ok
    assert report.states_analysed == 8
    assert report.transitions_fired == 39
    assert report.counter_example is None
    assert all(op.covered for op in report.operations)


def test_run_model_check_fails_on_an_unreachable_operation(tmp_path: Path) -> None:
    """Dead specification: every check probcli ran passed, and the report is not ok."""
    mock = _mock_run({"-init": _INIT, "-model_check": _MODEL_CHECK_UNCOVERED})
    with patch("subprocess.run", side_effect=mock):
        report = run_model_check(_spec(tmp_path), _BINARY)

    named = {c.name: c for c in report.checks}
    assert named["model_check"].status == CheckStatus.passed
    assert named["coverage"].status == CheckStatus.failed
    assert "Freeze" in named["coverage"].detail
    assert not report.ok


def test_run_model_check_fails_on_a_counter_example(tmp_path: Path) -> None:
    """probcli exits 0 here; only the transcript says a counter-example was found."""
    mock = _mock_run(
        {"-init": _INIT, "-model_check": _MODEL_CHECK_COUNTER_EXAMPLE}, returncode=0
    )
    with patch("subprocess.run", side_effect=mock):
        report = run_model_check(_spec(tmp_path), _BINARY)

    assert not report.ok
    assert report.counter_example is not None
    assert report.counter_example.violation == "deadlock"
    assert [s.operation for s in report.counter_example.steps] == ["INITIALISATION"]


def test_run_model_check_fails_when_no_census_was_printed(tmp_path: Path) -> None:
    """A run whose output carries no census answered nothing, so nothing is covered."""
    censusless = _MODEL_CHECK_COVERED.split("Coverage:")[0]
    mock = _mock_run({"-init": _INIT, "-model_check": censusless})
    with patch("subprocess.run", side_effect=mock):
        report = run_model_check(_spec(tmp_path), _BINARY)

    assert report.operations == []
    assert not report.ok


# ---------------------------------------------------------------------------
# full suite
# ---------------------------------------------------------------------------


def test_run_full_suite(tmp_path: Path) -> None:
    mock = _mock_run(
        {
            "-init": _INIT,
            "-animate": _ANIMATE,
            "-cbc_assertions": _CBC_ASSERTIONS,
            "-cbc_deadlock": _CBC_DEADLOCK,
            "-model_check": _MODEL_CHECK_COVERED,
        }
    )
    with patch("subprocess.run", side_effect=mock):
        report = run_full_suite(_spec(tmp_path), _BINARY)

    assert [c.name for c in report.checks] == [
        "init",
        "animate",
        "cbc_assertions",
        "cbc_deadlock",
        "model_check",
        "coverage",
    ]
    assert report.ok
    assert report.states_analysed == 8
    # probcli announces no version banner on these runs, and the report says so
    # rather than naming one it never read.
    assert report.probcli_version == "unknown"


def test_full_suite_takes_coverage_from_the_exhaustive_run(tmp_path: Path) -> None:
    """The animate run leaves ClearHighlight unfired; the model check does not."""
    mock = _mock_run(
        {
            "-init": _INIT,
            "-animate": _ANIMATE,
            "-cbc_assertions": _CBC_ASSERTIONS,
            "-cbc_deadlock": _CBC_DEADLOCK,
            "-model_check": _MODEL_CHECK_COVERED,
        }
    )
    with patch("subprocess.run", side_effect=mock):
        report = run_full_suite(_spec(tmp_path), _BINARY)

    counts = {op.name: op.times_fired for op in report.operations}
    assert counts["ClearHighlight"] == 1
    assert report.ok
