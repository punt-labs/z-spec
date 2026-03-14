"""Report I/O — save/load <stem>.<type>.json alongside .tex files.

Convention:
    <stem>.report.json    — ProB verification report
    <stem>.fuzz.json      — Fuzz type-check result
    <stem>.partition.json — TTF partition report
    <stem>.audit.json     — Test coverage audit report
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def report_path(tex_path: Path) -> Path:
    """Return the ProB report path for a given .tex file."""
    return tex_path.parent / (tex_path.stem + ".report.json")


def fuzz_path(tex_path: Path) -> Path:
    """Return the fuzz result path for a given .tex file."""
    return tex_path.parent / (tex_path.stem + ".fuzz.json")


def partition_path(tex_path: Path) -> Path:
    """Return the partition report path for a given .tex file."""
    return tex_path.parent / (tex_path.stem + ".partition.json")


def audit_path(tex_path: Path) -> Path:
    """Return the audit report path for a given .tex file."""
    return tex_path.parent / (tex_path.stem + ".audit.json")


def is_stale(tex_path: Path) -> bool:
    """Check if the ProB report is older than the .tex source."""
    rpt = report_path(tex_path)
    if not rpt.exists():
        return True
    return tex_path.stat().st_mtime > rpt.stat().st_mtime


# ---------------------------------------------------------------------------
# Save helpers
# ---------------------------------------------------------------------------


def _save_json(path: Path, data: dict[str, Any]) -> Path:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# ProB report
# ---------------------------------------------------------------------------


def save_report(tex_path: Path, report: ProbReport) -> Path:
    """Save a ProbReport as JSON alongside the .tex file."""
    return _save_json(report_path(tex_path), report.to_dict())


def load_report(tex_path: Path) -> ProbReport | None:
    """Load a ProbReport from disk. Returns None if missing or corrupt."""
    rpt = report_path(tex_path)
    if not rpt.exists():
        return None
    try:
        data: dict[str, Any] = json.loads(rpt.read_text(encoding="utf-8"))
        return prob_from_dict(data)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None


def prob_from_dict(data: dict[str, Any]) -> ProbReport:
    """Reconstruct a ProbReport from a JSON-loaded dict."""
    checks = [
        CheckResult(
            name=c["name"],
            status=CheckStatus(c["status"]),
            detail=c.get("detail", ""),
        )
        for c in data.get("checks", [])
    ]

    operations = [
        OperationCoverage(
            name=o["name"],
            times_fired=o["times_fired"],
            covered=o["covered"],
        )
        for o in data.get("operations", [])
    ]

    counter_example = None
    if data.get("counter_example") is not None:
        ce = data["counter_example"]
        steps = [
            TraceStep(
                step_number=s["step_number"],
                operation=s["operation"],
                state=s.get("state", {}),
            )
            for s in ce.get("steps", [])
        ]
        counter_example = CounterExample(steps=steps, violation=ce.get("violation", ""))

    return ProbReport(
        timestamp=data.get("timestamp", ""),
        probcli_version=data.get("probcli_version", ""),
        setsize=data.get("setsize", 0),
        checks=checks,
        operations=operations,
        counter_example=counter_example,
        states_analysed=data.get("states_analysed", 0),
        transitions_fired=data.get("transitions_fired", 0),
    )


# ---------------------------------------------------------------------------
# Fuzz result
# ---------------------------------------------------------------------------


def save_fuzz(tex_path: Path, result: FuzzResult) -> Path:
    """Save a FuzzResult as JSON alongside the .tex file."""
    return _save_json(fuzz_path(tex_path), result.to_dict())


def load_fuzz(tex_path: Path) -> FuzzResult | None:
    """Load a FuzzResult from disk. Returns None if missing or corrupt."""
    fp = fuzz_path(tex_path)
    if not fp.exists():
        return None
    try:
        data: dict[str, Any] = json.loads(fp.read_text(encoding="utf-8"))
        return fuzz_from_dict(data)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None


def fuzz_from_dict(data: dict[str, Any]) -> FuzzResult:
    errors = [
        FuzzError(line=e["line"], column=e["column"], message=e["message"])
        for e in data.get("errors", [])
    ]
    return FuzzResult(ok=data["ok"], errors=errors)


# ---------------------------------------------------------------------------
# Partition report
# ---------------------------------------------------------------------------


def save_partition(tex_path: Path, report: PartitionReport) -> Path:
    """Save a PartitionReport as JSON alongside the .tex file."""
    return _save_json(partition_path(tex_path), report.to_dict())


def load_partition(tex_path: Path) -> PartitionReport | None:
    """Load a PartitionReport from disk. Returns None if missing or corrupt."""
    pp = partition_path(tex_path)
    if not pp.exists():
        return None
    try:
        data: dict[str, Any] = json.loads(pp.read_text(encoding="utf-8"))
        return partition_from_dict(data)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None


def partition_from_dict(data: dict[str, Any]) -> PartitionReport:
    operations: list[OperationPartitions] = []
    for op_data in data.get("operations", []):
        partitions = [
            Partition(
                id=p["id"],
                class_name=p["class"],
                branch=p.get("branch"),
                status=PartitionStatus(p["status"]),
                inputs=p.get("inputs", {}),
                pre_state=p.get("preState", {}),
                post_state=p.get("postState"),
                notes=p.get("notes", ""),
            )
            for p in op_data.get("partitions", [])
        ]
        operations.append(
            OperationPartitions(
                name=op_data["name"],
                kind=op_data.get("kind", "delta"),
                inputs=op_data.get("inputs", []),
                state_vars=op_data.get("stateVars", []),
                branches=op_data.get("branches", []),
                partitions=partitions,
            )
        )
    return PartitionReport(
        specification=data.get("specification", ""),
        timestamp=data.get("timestamp", ""),
        operations=operations,
    )


# ---------------------------------------------------------------------------
# Audit report
# ---------------------------------------------------------------------------


def save_audit(tex_path: Path, report: AuditReport) -> Path:
    """Save an AuditReport as JSON alongside the .tex file."""
    return _save_json(audit_path(tex_path), report.to_dict())


def load_audit(tex_path: Path) -> AuditReport | None:
    """Load an AuditReport from disk. Returns None if missing or corrupt."""
    ap = audit_path(tex_path)
    if not ap.exists():
        return None
    try:
        data: dict[str, Any] = json.loads(ap.read_text(encoding="utf-8"))
        return audit_from_dict(data)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None


def audit_from_dict(data: dict[str, Any]) -> AuditReport:
    constraints = [
        AuditConstraint(
            text=c["text"],
            category=c["category"],
            source=c["source"],
            covered_by=c.get("coveredBy"),
            confidence=(
                AuditConfidence(c["confidence"]) if c.get("confidence") else None
            ),
        )
        for c in data.get("constraints", [])
    ]
    uncovered = [
        AuditSuggestion(
            text=u["text"],
            category=u["category"],
            source=u["source"],
            suggestion=u["suggestion"],
            test_pattern=u.get("testPattern", ""),
        )
        for u in data.get("uncovered", [])
    ]
    return AuditReport(
        specification=data.get("specification", ""),
        test_directory=data.get("testDirectory", ""),
        timestamp=data.get("timestamp", ""),
        constraints=constraints,
        uncovered=uncovered,
    )
