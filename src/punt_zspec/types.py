"""Domain types for punt-zspec."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class BlockKind(StrEnum):
    """Kind of Z notation block."""

    schema = "schema"
    zed = "zed"
    axdef = "axdef"
    gendef = "gendef"


class CheckStatus(StrEnum):
    """Status of a single probcli check."""

    passed = "passed"
    failed = "failed"
    warning = "warning"
    skipped = "skipped"


@dataclass(frozen=True)
class ZBlock:
    """A single Z notation block extracted from a .tex file."""

    kind: BlockKind
    name: str  # schema name, or "" for zed/axdef/gendef
    declarations: str  # text before \where (or entire body for zed)
    predicates: str  # text after \where (empty if no \where)
    section: str  # enclosing \section{} title
    line_number: int  # 1-based line number in source


@dataclass(frozen=True)
class SpecModel:
    """Parsed Z specification."""

    title: str
    sections: list[str]
    blocks: list[ZBlock]
    source_path: str

    def blocks_by_section(self) -> dict[str, list[ZBlock]]:
        """Group blocks by their enclosing section."""
        result: dict[str, list[ZBlock]] = {}
        for block in self.blocks:
            result.setdefault(block.section, []).append(block)
        return result

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "sections": self.sections,
            "blocks": [
                {
                    "kind": b.kind.value,
                    "name": b.name,
                    "declarations": b.declarations,
                    "predicates": b.predicates,
                    "section": b.section,
                    "line_number": b.line_number,
                }
                for b in self.blocks
            ],
            "source_path": self.source_path,
        }


@dataclass(frozen=True)
class FuzzError:
    """A single fuzz type-checking error."""

    line: int
    column: int
    message: str


@dataclass(frozen=True)
class FuzzResult:
    """Result of running fuzz -t."""

    ok: bool
    errors: list[FuzzError] = field(default_factory=list)  # pyright: ignore[reportUnknownVariableType]
    raw_output: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "errors": [
                {"line": e.line, "column": e.column, "message": e.message}
                for e in self.errors
            ],
        }


@dataclass(frozen=True)
class CheckResult:
    """Result of a single probcli check."""

    name: str
    status: CheckStatus
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class OperationCoverage:
    """Coverage data for a single Z operation."""

    name: str
    times_fired: int
    covered: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "times_fired": self.times_fired,
            "covered": self.covered,
        }


@dataclass(frozen=True)
class CounterExample:
    """A counter-example trace from probcli."""

    steps: list[TraceStep]
    violation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "steps": [s.to_dict() for s in self.steps],
            "violation": self.violation,
        }


@dataclass(frozen=True)
class TraceStep:
    """A single step in a counter-example trace."""

    step_number: int
    operation: str
    state: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_number": self.step_number,
            "operation": self.operation,
            "state": self.state,
        }


@dataclass(frozen=True)
class ProbReport:
    """Complete ProB verification report."""

    timestamp: str  # ISO 8601
    probcli_version: str
    setsize: int
    checks: list[CheckResult]
    operations: list[OperationCoverage]
    counter_example: CounterExample | None
    states_analysed: int
    transitions_fired: int

    @property
    def ok(self) -> bool:
        return all(
            c.status in (CheckStatus.passed, CheckStatus.skipped, CheckStatus.warning)
            for c in self.checks
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "timestamp": self.timestamp,
            "probcli_version": self.probcli_version,
            "setsize": self.setsize,
            "ok": self.ok,
            "states_analysed": self.states_analysed,
            "transitions_fired": self.transitions_fired,
            "checks": [c.to_dict() for c in self.checks],
            "operations": [o.to_dict() for o in self.operations],
        }
        if self.counter_example is not None:
            result["counter_example"] = self.counter_example.to_dict()
        return result


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
