"""The ProB verification report and the check and coverage results it carries."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from punt_zspec.types.trace import CounterExample


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
    """One Z operation as probcli's coverage census counted it.

    Coverage is derived, never stored: an operation is covered because the
    census counted it firing. "Covered but never fired" is not a state this
    type can be put into.
    """

    name: str
    times_fired: int

    @property
    def covered(self) -> bool:
        """Return whether probcli fired this operation at least once."""
        return self.times_fired > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "times_fired": self.times_fired,
            "covered": self.covered,
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
        """Return whether every check reached a verdict that can be relied on.

        ``warning`` does not count. It marks a run that finished without
        finding anything and without certifying it looked everywhere, and an
        unestablished claim is not a passing one — the gate would otherwise
        report success on the strength of a partial exploration.
        """
        return all(
            c.status in (CheckStatus.passed, CheckStatus.skipped) for c in self.checks
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
