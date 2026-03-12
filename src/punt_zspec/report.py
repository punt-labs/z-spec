"""ProB report I/O — save/load <stem>.report.json alongside .tex files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from punt_zspec.types import (
    CheckResult,
    CheckStatus,
    CounterExample,
    OperationCoverage,
    ProbReport,
    TraceStep,
)


def report_path(tex_path: Path) -> Path:
    """Return the report path for a given .tex file."""
    return tex_path.with_suffix(".report.json")


def save_report(tex_path: Path, report: ProbReport) -> Path:
    """Save a ProbReport as JSON alongside the .tex file."""
    out = report_path(tex_path)
    out.write_text(json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8")
    return out


def load_report(tex_path: Path) -> ProbReport | None:
    """Load a ProbReport from disk. Returns None if no report exists."""
    rpt = report_path(tex_path)
    if not rpt.exists():
        return None
    data: dict[str, Any] = json.loads(rpt.read_text(encoding="utf-8"))
    return _from_dict(data)


def is_stale(tex_path: Path) -> bool:
    """Check if the report is older than the .tex source."""
    rpt = report_path(tex_path)
    if not rpt.exists():
        return True
    return tex_path.stat().st_mtime > rpt.stat().st_mtime


def _from_dict(data: dict[str, Any]) -> ProbReport:
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
