"""Tests for punt_zspec.report."""

from __future__ import annotations

import os
from pathlib import Path

from punt_zspec.report import is_stale, load_report, report_path, save_report
from punt_zspec.types import (
    CheckResult,
    CheckStatus,
    CounterExample,
    OperationCoverage,
    ProbReport,
    TraceStep,
)


def _make_report() -> ProbReport:
    return ProbReport(
        timestamp="2026-03-12T00:00:00Z",
        probcli_version="1.13.1",
        setsize=2,
        checks=[
            CheckResult(name="init", status=CheckStatus.passed, detail="OK"),
            CheckResult(
                name="model_check", status=CheckStatus.passed, detail="10 states"
            ),
        ],
        operations=[
            OperationCoverage(name="AddItem", times_fired=5, covered=True),
            OperationCoverage(name="RemoveItem", times_fired=0, covered=False),
        ],
        counter_example=None,
        states_analysed=10,
        transitions_fired=25,
    )


def test_report_path() -> None:
    p = report_path(Path("examples/claude-code.tex"))
    assert p == Path("examples/claude-code.report.json")


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    tex = tmp_path / "spec.tex"
    tex.write_text("dummy")
    report = _make_report()

    saved = save_report(tex, report)
    assert saved.exists()

    loaded = load_report(tex)
    assert loaded is not None
    assert loaded.ok
    assert loaded.timestamp == "2026-03-12T00:00:00Z"
    assert loaded.probcli_version == "1.13.1"
    assert loaded.setsize == 2
    assert loaded.states_analysed == 10
    assert loaded.transitions_fired == 25
    assert len(loaded.checks) == 2
    assert len(loaded.operations) == 2
    assert loaded.operations[0].name == "AddItem"
    assert loaded.operations[1].covered is False
    assert loaded.counter_example is None


def test_load_report_missing(tmp_path: Path) -> None:
    tex = tmp_path / "missing.tex"
    assert load_report(tex) is None


def test_is_stale_when_no_report(tmp_path: Path) -> None:
    tex = tmp_path / "spec.tex"
    tex.write_text("dummy")
    assert is_stale(tex) is True


def test_is_stale_when_tex_newer(tmp_path: Path) -> None:
    tex = tmp_path / "spec.tex"
    tex.write_text("dummy")
    save_report(tex, _make_report())
    # Set tex mtime 10 seconds ahead of report to guarantee staleness
    rpt_path = tmp_path / "spec.report.json"
    rpt_mtime = rpt_path.stat().st_mtime
    os.utime(tex, (rpt_mtime + 10, rpt_mtime + 10))
    assert is_stale(tex) is True


def test_is_stale_when_report_newer(tmp_path: Path) -> None:
    tex = tmp_path / "spec.tex"
    tex.write_text("dummy")
    save_report(tex, _make_report())
    # Set tex mtime 10 seconds before report to guarantee freshness
    rpt_path = tmp_path / "spec.report.json"
    rpt_mtime = rpt_path.stat().st_mtime
    os.utime(tex, (rpt_mtime - 10, rpt_mtime - 10))
    assert is_stale(tex) is False


def test_counter_example_roundtrip(tmp_path: Path) -> None:
    tex = tmp_path / "spec.tex"
    tex.write_text("dummy")
    report = ProbReport(
        timestamp="2026-03-12T00:00:00Z",
        probcli_version="1.13.1",
        setsize=2,
        checks=[
            CheckResult(
                name="model_check", status=CheckStatus.failed, detail="violation"
            ),
        ],
        operations=[],
        counter_example=CounterExample(
            steps=[
                TraceStep(step_number=0, operation="INITIALISATION", state={"x": "0"}),
                TraceStep(step_number=1, operation="Increment", state={"x": "11"}),
            ],
            violation="x ≤ 10",
        ),
        states_analysed=5,
        transitions_fired=8,
    )

    save_report(tex, report)
    loaded = load_report(tex)
    assert loaded is not None
    assert not loaded.ok
    assert loaded.counter_example is not None
    assert len(loaded.counter_example.steps) == 2
    assert loaded.counter_example.steps[1].operation == "Increment"
    assert loaded.counter_example.violation == "x ≤ 10"
