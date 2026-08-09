"""Wrapper for the probcli model checker."""

from __future__ import annotations

import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from punt_zspec.prob_output import ProbOutput
from punt_zspec.types import CheckResult, ProbReport

# probcli reports which operations fired only when asked. Every run whose
# report carries coverage passes this flag; a run without it has no census,
# and no census is a failed coverage check rather than a silent pass.
_COVERAGE = "-coverage"


def resolve_probcli() -> Path | None:
    """Find the probcli binary. Check $PROBCLI, then PATH, then ~/Applications."""
    env = os.environ.get("PROBCLI")
    if env:
        p = Path(env)
        if p.is_file():
            return p
    found = shutil.which("probcli")
    if found:
        return Path(found)
    # Conventional install location
    home_path = Path.home() / "Applications" / "ProB" / "probcli"
    if home_path.is_file():
        return home_path
    return None


def _run_probcli(
    binary: Path,
    tex_path: Path,
    args: list[str],
    timeout_s: int = 120,
) -> ProbOutput:
    """Run probcli with given arguments and return its output."""
    cmd = [str(binary), str(tex_path), *args]
    return ProbOutput.of(
        subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    )


def _model_check_args(setsize: int, max_ops: int, timeout_ms: int) -> list[str]:
    """Return the probcli arguments for a coverage-reporting model check."""
    return [
        "-model_check",
        "-p",
        "DEFAULT_SETSIZE",
        str(setsize),
        "-p",
        "MAX_OPERATIONS",
        str(max_ops),
        "-p",
        "TIME_OUT",
        str(timeout_ms),
        _COVERAGE,
    ]


def run_init(tex_path: Path, binary: Path, setsize: int = 2) -> ProbOutput:
    """Run probcli -init and return its output."""
    return _run_probcli(
        binary, tex_path, ["-init", "-p", "DEFAULT_SETSIZE", str(setsize)]
    )


def run_animate(
    tex_path: Path,
    binary: Path,
    steps: int = 20,
    setsize: int = 2,
) -> ProbReport:
    """Run probcli -animate and return a partial report."""
    init = run_init(tex_path, binary, setsize)
    animate = _run_probcli(
        binary,
        tex_path,
        ["-animate", str(steps), "-p", "DEFAULT_SETSIZE", str(setsize), _COVERAGE],
    )
    coverage = animate.coverage()

    return ProbReport(
        timestamp=datetime.now(UTC).isoformat(),
        probcli_version=init.version,
        setsize=setsize,
        checks=[init.check("init"), animate.check("animate"), coverage.check()],
        operations=list(coverage.operations),
        counter_example=None,
        states_analysed=animate.states_analysed,
        transitions_fired=animate.transitions_fired,
    )


def run_model_check(
    tex_path: Path,
    binary: Path,
    setsize: int = 2,
    max_ops: int = 1000,
    timeout_ms: int = 30000,
) -> ProbReport:
    """Run probcli -model_check and return a partial report."""
    init = run_init(tex_path, binary, setsize)
    checked = _run_probcli(
        binary,
        tex_path,
        _model_check_args(setsize, max_ops, timeout_ms),
        timeout_s=max(timeout_ms // 1000 + 30, 60),
    )
    coverage = checked.coverage()

    return ProbReport(
        timestamp=datetime.now(UTC).isoformat(),
        probcli_version=init.version,
        setsize=setsize,
        checks=[init.check("init"), checked.check("model_check"), coverage.check()],
        operations=list(coverage.operations),
        counter_example=checked.counter_example(),
        states_analysed=checked.states_analysed,
        transitions_fired=checked.transitions_fired,
    )


def run_full_suite(
    tex_path: Path,
    binary: Path,
    setsize: int = 2,
    max_ops: int = 1000,
    timeout_ms: int = 30000,
) -> ProbReport:
    """Run all five probcli checks and return a complete report."""
    init = run_init(tex_path, binary, setsize)
    animate = _run_probcli(
        binary,
        tex_path,
        ["-animate", "20", "-p", "DEFAULT_SETSIZE", str(setsize)],
    )
    cbc_assert = _run_probcli(binary, tex_path, ["-cbc_assertions"])
    cbc_dead = _run_probcli(binary, tex_path, ["-cbc_deadlock"])
    checked = _run_probcli(
        binary,
        tex_path,
        _model_check_args(setsize, max_ops, timeout_ms),
        timeout_s=max(timeout_ms // 1000 + 30, 60),
    )

    # The exhaustive model check is the run that decides coverage: it explores
    # the whole reachable state space, so an operation it never fired is one no
    # reachable state enables.
    coverage = checked.coverage()
    checks: list[CheckResult] = [
        init.check("init"),
        animate.check("animate"),
        cbc_assert.check("cbc_assertions"),
        cbc_dead.check("cbc_deadlock"),
        checked.check("model_check"),
        coverage.check(),
    ]

    return ProbReport(
        timestamp=datetime.now(UTC).isoformat(),
        probcli_version=init.version,
        setsize=setsize,
        checks=checks,
        operations=list(coverage.operations),
        counter_example=checked.counter_example(),
        states_analysed=checked.states_analysed,
        transitions_fired=checked.transitions_fired,
    )
