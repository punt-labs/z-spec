"""Tests for punt_zspec.report."""

from __future__ import annotations

import os
from pathlib import Path

from punt_zspec.report import (
    audit_path,
    fuzz_path,
    is_stale,
    load_audit,
    load_fuzz,
    load_partition,
    load_report,
    partition_path,
    report_path,
    save_audit,
    save_fuzz,
    save_partition,
    save_report,
)
from punt_zspec.types import (
    AuditConfidence,
    AuditConstraint,
    AuditReport,
    AuditSuggestion,
    CheckResult,
    CheckStatus,
    CounterExample,
    FuzzError,
    FuzzResult,
    OperationCoverage,
    OperationPartitions,
    Partition,
    PartitionReport,
    PartitionStatus,
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


# ---------------------------------------------------------------------------
# Fuzz report
# ---------------------------------------------------------------------------


def test_fuzz_path() -> None:
    p = fuzz_path(Path("examples/claude-code.tex"))
    assert p == Path("examples/claude-code.fuzz.json")


def test_fuzz_roundtrip(tmp_path: Path) -> None:
    tex = tmp_path / "spec.tex"
    tex.write_text("dummy")
    result = FuzzResult(
        ok=False,
        errors=[FuzzError(line=10, column=5, message="undeclared identifier")],
    )
    save_fuzz(tex, result)
    loaded = load_fuzz(tex)
    assert loaded is not None
    assert not loaded.ok
    assert len(loaded.errors) == 1
    assert loaded.errors[0].message == "undeclared identifier"


def test_load_fuzz_missing(tmp_path: Path) -> None:
    assert load_fuzz(tmp_path / "missing.tex") is None


# ---------------------------------------------------------------------------
# Partition report
# ---------------------------------------------------------------------------


def test_partition_path() -> None:
    p = partition_path(Path("examples/claude-code.tex"))
    assert p == Path("examples/claude-code.partition.json")


def test_partition_roundtrip(tmp_path: Path) -> None:
    tex = tmp_path / "spec.tex"
    tex.write_text("dummy")
    report = PartitionReport(
        specification="spec.tex",
        timestamp="2026-03-12T00:00:00Z",
        operations=[
            OperationPartitions(
                name="Increment",
                kind="delta",
                inputs=[{"name": "n", "type": "nat"}],
                state_vars=["x"],
                branches=[{"id": 1, "description": "Normal", "condition": "x < 10"}],
                partitions=[
                    Partition(
                        id=1,
                        class_name="happy-path",
                        branch=1,
                        status=PartitionStatus.accepted,
                        inputs={"n": 1},
                        pre_state={"x": 5},
                        post_state={"x": 6},
                    ),
                    Partition(
                        id=2,
                        class_name="rejected",
                        branch=None,
                        status=PartitionStatus.rejected,
                        inputs={"n": 1},
                        pre_state={"x": 10},
                        post_state=None,
                        notes="Precondition fails",
                    ),
                ],
            )
        ],
    )
    save_partition(tex, report)
    loaded = load_partition(tex)
    assert loaded is not None
    assert loaded.specification == "spec.tex"
    assert len(loaded.operations) == 1
    op = loaded.operations[0]
    assert op.name == "Increment"
    assert len(op.partitions) == 2
    assert op.partitions[0].class_name == "happy-path"
    assert op.partitions[0].post_state == {"x": 6}
    assert op.partitions[1].status == PartitionStatus.rejected
    assert op.partitions[1].post_state is None
    assert op.summary == {"total": 2, "accepted": 1, "rejected": 1, "pruned": 0}


def test_load_partition_missing(tmp_path: Path) -> None:
    assert load_partition(tmp_path / "missing.tex") is None


# ---------------------------------------------------------------------------
# Audit report
# ---------------------------------------------------------------------------


def test_audit_path() -> None:
    p = audit_path(Path("examples/claude-code.tex"))
    assert p == Path("examples/claude-code.audit.json")


def test_audit_roundtrip(tmp_path: Path) -> None:
    tex = tmp_path / "spec.tex"
    tex.write_text("dummy")
    report = AuditReport(
        specification="spec.tex",
        test_directory="tests/",
        timestamp="2026-03-12T00:00:00Z",
        constraints=[
            AuditConstraint(
                text="x <= 10",
                category="invariant",
                source="State",
                covered_by="test_state.py:15",
                confidence=AuditConfidence.high,
            ),
        ],
        uncovered=[
            AuditSuggestion(
                text="x >= 0",
                category="invariant",
                source="State",
                suggestion="Test lower bound",
                test_pattern="assert x >= 0",
            ),
        ],
    )
    save_audit(tex, report)
    loaded = load_audit(tex)
    assert loaded is not None
    assert loaded.specification == "spec.tex"
    assert loaded.test_directory == "tests/"
    assert len(loaded.constraints) == 1
    assert loaded.constraints[0].covered_by == "test_state.py:15"
    assert loaded.constraints[0].confidence == AuditConfidence.high
    assert len(loaded.uncovered) == 1
    assert loaded.uncovered[0].suggestion == "Test lower bound"
    assert loaded.percentage == 50  # 1 covered out of 2 total


def test_load_audit_missing(tmp_path: Path) -> None:
    assert load_audit(tmp_path / "missing.tex") is None
