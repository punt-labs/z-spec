"""Domain types for punt-zspec."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
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
