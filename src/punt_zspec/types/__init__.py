"""Domain types for punt-zspec."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, final

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
# Audit report types (LLM-generated, validated and saved by MCP tool)
# ---------------------------------------------------------------------------


class AuditConfidence(StrEnum):
    """Confidence level for a test coverage match."""

    high = "high"
    medium = "medium"
    low = "low"


@dataclass(frozen=True)
class AuditConstraint:
    """A single constraint with its test coverage status."""

    text: str
    category: str  # "invariant", "precondition", "effect", "bound"
    source: str  # schema name
    covered_by: str | None = None  # e.g. "FooTests.swift:89"
    confidence: AuditConfidence | None = None

    @property
    def covered(self) -> bool:
        return self.covered_by is not None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "text": self.text,
            "category": self.category,
            "source": self.source,
        }
        if self.covered_by is not None:
            result["coveredBy"] = self.covered_by
        if self.confidence is not None:
            result["confidence"] = self.confidence.value
        return result


@dataclass(frozen=True)
class AuditSuggestion:
    """A suggested test for an uncovered constraint."""

    text: str
    category: str
    source: str
    suggestion: str
    test_pattern: str = ""

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "text": self.text,
            "category": self.category,
            "source": self.source,
            "suggestion": self.suggestion,
        }
        if self.test_pattern:
            result["testPattern"] = self.test_pattern
        return result


@dataclass(frozen=True)
class AuditReport:
    """Complete test coverage audit report."""

    specification: str
    test_directory: str
    timestamp: str  # ISO 8601
    constraints: list[AuditConstraint]
    uncovered: list[AuditSuggestion]

    @property
    def total(self) -> int:
        return len(self.constraints) + len(self.uncovered)

    @property
    def covered_count(self) -> int:
        return sum(1 for c in self.constraints if c.covered)

    @property
    def percentage(self) -> int:
        return round(self.covered_count * 100 / self.total) if self.total else 0

    @property
    def by_category(self) -> dict[str, dict[str, int]]:
        cats: dict[str, dict[str, int]] = {}
        for c in self.constraints:
            entry = cats.setdefault(c.category, {"covered": 0, "total": 0})
            entry["total"] += 1
            if c.covered:
                entry["covered"] += 1
        for u in self.uncovered:
            entry = cats.setdefault(u.category, {"covered": 0, "total": 0})
            entry["total"] += 1
        return cats

    def to_dict(self) -> dict[str, Any]:
        return {
            "specification": self.specification,
            "testDirectory": self.test_directory,
            "timestamp": self.timestamp,
            "summary": {
                "covered": self.covered_count,
                "total": self.total,
                "percentage": self.percentage,
            },
            "byCategory": self.by_category,
            "constraints": [c.to_dict() for c in self.constraints],
            "uncovered": [u.to_dict() for u in self.uncovered],
        }


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
