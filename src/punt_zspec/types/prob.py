"""ProB verification report and its constituent check and trace types."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class CheckStatus(StrEnum):
    """Status of a single probcli check."""

    passed = "passed"
    failed = "failed"
    warning = "warning"
    skipped = "skipped"


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
