"""Domain types for punt-zspec."""

from __future__ import annotations

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
from .reports import SpecReports
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
