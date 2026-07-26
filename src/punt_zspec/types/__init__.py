"""Domain types for punt-zspec."""

from __future__ import annotations

from dataclasses import dataclass
from typing import final

from .audit import AuditConfidence, AuditConstraint, AuditReport, AuditSuggestion
from .fuzz import FuzzError, FuzzResult
from .partition import (
    OperationPartitions,
    Partition,
    PartitionReport,
    PartitionStatus,
)
from .prob import (
    CheckResult,
    CheckStatus,
    CounterExample,
    OperationCoverage,
    ProbReport,
    TraceStep,
)
from .spec import BlockKind, SpecModel, ZBlock
from .tutorial import Collection, Lesson

__all__ = [
    "AuditConfidence",
    "AuditConstraint",
    "AuditReport",
    "AuditSuggestion",
    "BlockKind",
    "CheckResult",
    "CheckStatus",
    "Collection",
    "CounterExample",
    "FuzzError",
    "FuzzResult",
    "Lesson",
    "OperationCoverage",
    "OperationPartitions",
    "Partition",
    "PartitionReport",
    "PartitionStatus",
    "ProbReport",
    "SpecModel",
    "SpecReports",
    "TraceStep",
    "ZBlock",
]


# ---------------------------------------------------------------------------
# Persisted-report bundle
# ---------------------------------------------------------------------------


@final
@dataclass(frozen=True, slots=True)
class SpecReports:
    """A frozen snapshot of the four reports persisted beside a spec.

    Each field is optional because a spec may have no report of that kind yet —
    absence is the documented contract, not a failure (PY-TS-14).
    """

    report: ProbReport | None
    fuzz: FuzzResult | None
    partition: PartitionReport | None
    audit: AuditReport | None
