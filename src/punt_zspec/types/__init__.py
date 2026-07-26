"""Domain types for punt-zspec."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, final

from .fuzz import FuzzError, FuzzResult
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
# Partition report types (LLM-generated, validated and saved by MCP tool)
# ---------------------------------------------------------------------------


class PartitionStatus(StrEnum):
    """Status of a single test partition."""

    accepted = "accepted"
    rejected = "rejected"
    pruned = "pruned"


@dataclass(frozen=True)
class Partition:
    """A single test partition derived from TTF analysis."""

    id: int
    class_name: str  # "happy-path", "boundary: min input", "rejected", etc.
    branch: int | None  # which behavioral branch, None for rejected/pruned
    status: PartitionStatus
    inputs: dict[str, Any]
    pre_state: dict[str, Any]
    post_state: dict[str, Any] | None
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": self.id,
            "class": self.class_name,
            "status": self.status.value,
            "inputs": self.inputs,
            "preState": self.pre_state,
            "notes": self.notes,
        }
        if self.branch is not None:
            result["branch"] = self.branch
        if self.post_state is not None:
            result["postState"] = self.post_state
        return result


@dataclass(frozen=True)
class OperationPartitions:
    """Partition analysis for a single Z operation."""

    name: str
    kind: str  # "delta" or "xi"
    inputs: list[dict[str, Any]]  # [{"name": ..., "type": ..., "constraints": [...]}]
    state_vars: list[str]
    branches: list[dict[str, Any]]
    partitions: list[Partition]

    @property
    def summary(self) -> dict[str, int]:
        total = len(self.partitions)
        accepted = sum(
            1 for p in self.partitions if p.status == PartitionStatus.accepted
        )
        rejected = sum(
            1 for p in self.partitions if p.status == PartitionStatus.rejected
        )
        pruned = sum(1 for p in self.partitions if p.status == PartitionStatus.pruned)
        return {
            "total": total,
            "accepted": accepted,
            "rejected": rejected,
            "pruned": pruned,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "inputs": self.inputs,
            "stateVars": self.state_vars,
            "branches": self.branches,
            "partitions": [p.to_dict() for p in self.partitions],
            "summary": self.summary,
        }


@dataclass(frozen=True)
class PartitionReport:
    """Complete partition analysis report."""

    specification: str
    timestamp: str  # ISO 8601
    operations: list[OperationPartitions]

    @property
    def total_partitions(self) -> int:
        return sum(len(op.partitions) for op in self.operations)

    @property
    def total_accepted(self) -> int:
        return sum(
            1
            for op in self.operations
            for p in op.partitions
            if p.status == PartitionStatus.accepted
        )

    @property
    def total_rejected(self) -> int:
        return sum(
            1
            for op in self.operations
            for p in op.partitions
            if p.status == PartitionStatus.rejected
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "specification": self.specification,
            "timestamp": self.timestamp,
            "operations": [op.to_dict() for op in self.operations],
        }


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
