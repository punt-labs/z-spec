"""Tests for punt_zspec.prob."""

from __future__ import annotations

import subprocess
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

# Sample probcli output fragments
_INIT_OUTPUT = """\
ProB CLI Version 1.13.1
Z operation: AddItem
Z operation: RemoveItem
Z operation: Clear
"""

_ANIMATE_OUTPUT = """\
States analysed: 0
Transitions fired: 15
ALL OPERATIONS COVERED
"""

_MODEL_CHECK_PASS = """\
States analysed: 42
Transitions fired: 150
No counter example found, all open states visited
"""

_MODEL_CHECK_FAIL = """\
States analysed: 10
Transitions fired: 25
COUNTER EXAMPLE FOUND
0: INITIALISATION
1: AddItem
Invariant violation
"""

_CBC_ASSERT_NONE = "No ASSERTION to check\n"
_CBC_DEADLOCK_PASS = "No deadlock possible (all possible deadlock states explored)\n"


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


def _mock_run(outputs: dict[str, str]) -> Any:
    """Create a mock subprocess.run that returns different output based on args."""

    def mock(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        cmd = args[0] if args else kwargs.get("args", [])
        cmd_str = " ".join(str(c) for c in cmd)
        for key, output in outputs.items():
            if key in cmd_str:
                return subprocess.CompletedProcess(
                    args=cmd, returncode=0, stdout=output, stderr=""
                )
        return subprocess.CompletedProcess(
            args=cmd, returncode=0, stdout="OK\n", stderr=""
        )

    return mock


def test_run_init_success(tmp_path: Path) -> None:
    tex = tmp_path / "spec.tex"
    tex.write_text("dummy")
    binary = Path("/usr/bin/probcli")

    mock_result = subprocess.CompletedProcess(
        args=[], returncode=0, stdout=_INIT_OUTPUT, stderr=""
    )
    with patch("subprocess.run", return_value=mock_result):
        result, raw = run_init(tex, binary)

    assert result.status == CheckStatus.passed
    assert "AddItem" in raw


def test_run_animate(tmp_path: Path) -> None:
    tex = tmp_path / "spec.tex"
    tex.write_text("dummy")
    binary = Path("/usr/bin/probcli")

    mock = _mock_run({"-init": _INIT_OUTPUT, "-animate": _ANIMATE_OUTPUT})
    with patch("subprocess.run", side_effect=mock):
        report = run_animate(tex, binary)

    assert report.checks[1].status == CheckStatus.passed
    assert report.checks[1].detail == "all ops covered"
    # All 3 operations from init should be covered since ALL OPERATIONS COVERED
    assert all(op.covered for op in report.operations)


def test_run_model_check_pass(tmp_path: Path) -> None:
    tex = tmp_path / "spec.tex"
    tex.write_text("dummy")
    binary = Path("/usr/bin/probcli")

    mock = _mock_run({"-init": _INIT_OUTPUT, "-model_check": _MODEL_CHECK_PASS})
    with patch("subprocess.run", side_effect=mock):
        report = run_model_check(tex, binary)

    assert report.ok
    assert report.states_analysed == 42
    assert report.transitions_fired == 150
    assert report.counter_example is None


def test_run_model_check_fail(tmp_path: Path) -> None:
    tex = tmp_path / "spec.tex"
    tex.write_text("dummy")
    binary = Path("/usr/bin/probcli")

    def mock_fail(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        cmd = args[0] if args else kwargs.get("args", [])
        cmd_str = " ".join(str(c) for c in cmd)
        if "-model_check" in cmd_str:
            return subprocess.CompletedProcess(
                args=cmd, returncode=1, stdout=_MODEL_CHECK_FAIL, stderr=""
            )
        return subprocess.CompletedProcess(
            args=cmd, returncode=0, stdout=_INIT_OUTPUT, stderr=""
        )

    with patch("subprocess.run", side_effect=mock_fail):
        report = run_model_check(tex, binary)

    assert not report.ok
    assert report.counter_example is not None
    assert len(report.counter_example.steps) == 2


def test_run_full_suite(tmp_path: Path) -> None:
    tex = tmp_path / "spec.tex"
    tex.write_text("dummy")
    binary = Path("/usr/bin/probcli")

    mock = _mock_run(
        {
            "-init": _INIT_OUTPUT,
            "-animate": _ANIMATE_OUTPUT,
            "-cbc_assertions": _CBC_ASSERT_NONE,
            "-cbc_deadlock": _CBC_DEADLOCK_PASS,
            "-model_check": _MODEL_CHECK_PASS,
        }
    )
    with patch("subprocess.run", side_effect=mock):
        report = run_full_suite(tex, binary)

    assert report.ok
    assert len(report.checks) == 5
    assert report.checks[0].name == "init"
    assert report.checks[1].name == "animate"
    assert report.checks[2].name == "cbc_assertions"
    assert report.checks[3].name == "cbc_deadlock"
    assert report.checks[4].name == "model_check"
    assert report.states_analysed == 42
    assert report.probcli_version == "1.13.1"
