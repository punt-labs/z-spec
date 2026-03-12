"""Wrapper for the probcli model checker."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from punt_zspec.types import (
    CheckResult,
    CheckStatus,
    CounterExample,
    OperationCoverage,
    ProbReport,
    TraceStep,
)

_STATES_RE = re.compile(r"States\s+analysed:\s*(\d+)")
_TRANS_RE = re.compile(r"Transitions\s+fired:\s*(\d+)")
_OP_RE = re.compile(r"Z operation:\s*(\w+)")
_VERSION_RE = re.compile(r"ProB CLI.*?(\d+\.\d+\.\d+)")
_COUNTER_RE = re.compile(r"(?<!No )COUNTER\s*EXAMPLE\s*FOUND", re.IGNORECASE)
_STEP_RE = re.compile(r"(\d+):\s*(\w+)")


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
) -> subprocess.CompletedProcess[str]:
    """Run probcli with given arguments."""
    cmd = [str(binary), str(tex_path), *args]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout_s,
    )


def _extract_version(output: str) -> str:
    """Extract probcli version from output."""
    m = _VERSION_RE.search(output)
    return m.group(1) if m else "unknown"


def _extract_states(output: str) -> int:
    m = _STATES_RE.search(output)
    return int(m.group(1)) if m else 0


def _extract_transitions(output: str) -> int:
    m = _TRANS_RE.search(output)
    return int(m.group(1)) if m else 0


def _extract_operations(output: str) -> list[str]:
    """Extract Z operation names from probcli output."""
    return _OP_RE.findall(output)


def _parse_counter_example(output: str) -> CounterExample | None:
    """Parse counter-example trace from probcli output."""
    if not _COUNTER_RE.search(output):
        return None

    steps: list[TraceStep] = []
    lines = output.split("\n")
    violation = ""
    in_counter = False

    for line in lines:
        if _COUNTER_RE.search(line):
            in_counter = True
            continue
        if not in_counter:
            continue
        stripped = line.strip()
        if not stripped:
            continue
        step_match = _STEP_RE.match(stripped)
        if step_match:
            state: dict[str, str] = {}
            steps.append(
                TraceStep(
                    step_number=int(step_match.group(1)),
                    operation=step_match.group(2),
                    state=state,
                )
            )
        elif not violation:
            violation = stripped

    return CounterExample(steps=steps, violation=violation) if steps else None


def _check_result(name: str, output: str, returncode: int) -> CheckResult:
    """Build a CheckResult from probcli output."""
    lowered = output.lower()

    # Check for success patterns first (before counter-example detection)
    if "no counter example found" in lowered or "no counter-example" in lowered:
        detail_parts: list[str] = []
        states = _extract_states(output)
        trans = _extract_transitions(output)
        if states:
            detail_parts.append(f"{states} states")
        if trans:
            detail_parts.append(f"{trans} transitions")
        return CheckResult(
            name=name, status=CheckStatus.passed, detail=", ".join(detail_parts) or "OK"
        )

    if "all operations covered" in lowered:
        return CheckResult(
            name=name, status=CheckStatus.passed, detail="all ops covered"
        )

    if "no deadlock" in lowered:
        return CheckResult(name=name, status=CheckStatus.passed, detail="deadlock-free")

    if "no assertion" in lowered:
        return CheckResult(
            name=name, status=CheckStatus.skipped, detail="no assertions defined"
        )

    # Counter-example detection (after ruling out "no counter example found")
    if _COUNTER_RE.search(output):
        return CheckResult(
            name=name, status=CheckStatus.failed, detail=output.strip()[:200]
        )

    # Non-zero return code with no recognized pattern
    if returncode != 0:
        if "not all transitions" in lowered:
            return CheckResult(
                name=name, status=CheckStatus.warning, detail="incomplete exploration"
            )
        return CheckResult(
            name=name, status=CheckStatus.failed, detail=output.strip()[:200]
        )

    return CheckResult(name=name, status=CheckStatus.passed, detail="OK")


def _build_coverage(init_output: str, animate_output: str) -> list[OperationCoverage]:
    """Build operation coverage from init and animation output."""
    ops = _extract_operations(init_output)
    covered_ops: set[str] = set()

    # Parse animation output for fired operations
    for line in animate_output.split("\n"):
        for op in ops:
            if op in line and ("execute" in line.lower() or "fired" in line.lower()):
                covered_ops.add(op)

    # If ALL OPERATIONS COVERED appears, mark all as covered
    if "all operations covered" in animate_output.lower():
        covered_ops = set(ops)

    return [
        OperationCoverage(
            name=op,
            times_fired=1 if op in covered_ops else 0,
            covered=op in covered_ops,
        )
        for op in ops
    ]


def run_init(tex_path: Path, binary: Path, setsize: int = 2) -> tuple[CheckResult, str]:
    """Run probcli -init and return (result, raw_output)."""
    result = _run_probcli(
        binary, tex_path, ["-init", "-p", "DEFAULT_SETSIZE", str(setsize)]
    )
    raw = result.stdout + result.stderr
    return _check_result("init", raw, result.returncode), raw


def run_animate(
    tex_path: Path,
    binary: Path,
    steps: int = 20,
    setsize: int = 2,
) -> ProbReport:
    """Run probcli -animate and return a partial report."""
    init_result, init_output = run_init(tex_path, binary, setsize)
    result = _run_probcli(
        binary,
        tex_path,
        ["-animate", str(steps), "-p", "DEFAULT_SETSIZE", str(setsize)],
    )
    raw = result.stdout + result.stderr
    animate_check = _check_result("animate", raw, result.returncode)
    coverage = _build_coverage(init_output, raw)

    return ProbReport(
        timestamp=datetime.now(UTC).isoformat(),
        probcli_version=_extract_version(init_output + raw),
        setsize=setsize,
        checks=[init_result, animate_check],
        operations=coverage,
        counter_example=None,
        states_analysed=0,
        transitions_fired=_extract_transitions(raw),
    )


def run_model_check(
    tex_path: Path,
    binary: Path,
    setsize: int = 2,
    max_ops: int = 1000,
    timeout_ms: int = 30000,
) -> ProbReport:
    """Run probcli -model_check and return a partial report."""
    init_result, init_output = run_init(tex_path, binary, setsize)
    result = _run_probcli(
        binary,
        tex_path,
        [
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
        ],
        timeout_s=max(timeout_ms // 1000 + 30, 60),
    )
    raw = result.stdout + result.stderr
    mc_check = _check_result("model_check", raw, result.returncode)
    coverage = _build_coverage(init_output, raw)
    counter = _parse_counter_example(raw)

    return ProbReport(
        timestamp=datetime.now(UTC).isoformat(),
        probcli_version=_extract_version(init_output + raw),
        setsize=setsize,
        checks=[init_result, mc_check],
        operations=coverage,
        counter_example=counter,
        states_analysed=_extract_states(raw),
        transitions_fired=_extract_transitions(raw),
    )


def run_full_suite(
    tex_path: Path,
    binary: Path,
    setsize: int = 2,
    max_ops: int = 1000,
    timeout_ms: int = 30000,
) -> ProbReport:
    """Run all five probcli checks and return a complete report."""
    init_result, init_output = run_init(tex_path, binary, setsize)

    # Animate
    anim = _run_probcli(
        binary,
        tex_path,
        ["-animate", "20", "-p", "DEFAULT_SETSIZE", str(setsize)],
    )
    anim_raw = anim.stdout + anim.stderr
    anim_check = _check_result("animate", anim_raw, anim.returncode)

    # CBC assertions
    cbc_assert = _run_probcli(binary, tex_path, ["-cbc_assertions"])
    cbc_assert_raw = cbc_assert.stdout + cbc_assert.stderr
    cbc_assert_check = _check_result(
        "cbc_assertions", cbc_assert_raw, cbc_assert.returncode
    )

    # CBC deadlock
    cbc_dead = _run_probcli(binary, tex_path, ["-cbc_deadlock"])
    cbc_dead_raw = cbc_dead.stdout + cbc_dead.stderr
    cbc_dead_check = _check_result("cbc_deadlock", cbc_dead_raw, cbc_dead.returncode)

    # Model check
    mc = _run_probcli(
        binary,
        tex_path,
        [
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
        ],
        timeout_s=max(timeout_ms // 1000 + 30, 60),
    )
    mc_raw = mc.stdout + mc.stderr
    mc_check = _check_result("model_check", mc_raw, mc.returncode)

    all_raw = init_output + anim_raw + mc_raw
    coverage = _build_coverage(init_output, anim_raw + mc_raw)
    counter = _parse_counter_example(mc_raw)

    return ProbReport(
        timestamp=datetime.now(UTC).isoformat(),
        probcli_version=_extract_version(all_raw),
        setsize=setsize,
        checks=[init_result, anim_check, cbc_assert_check, cbc_dead_check, mc_check],
        operations=coverage,
        counter_example=counter,
        states_analysed=_extract_states(mc_raw),
        transitions_fired=_extract_transitions(mc_raw),
    )
