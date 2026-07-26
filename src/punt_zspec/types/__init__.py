"""Domain types for punt-zspec."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
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


# ---------------------------------------------------------------------------
# Tutorial browser types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Lesson:
    """A single lesson in a tutorial collection."""

    title: str
    spec_path: str  # relative to manifest directory
    annotation: str  # didactic markdown
    highlights: list[str]  # section/schema names to default-open
    order: int  # 0-based index


@dataclass(frozen=True)
class Collection:
    """A tutorial collection parsed from a manifest.toml."""

    title: str
    description: str
    lessons: list[Lesson]
    base_path: Path  # directory containing the manifest
