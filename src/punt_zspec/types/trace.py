"""The counter-example trace probcli prints when a check fails."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


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
class CounterExample:
    """A counter-example trace from probcli: the steps, and what they broke."""

    steps: list[TraceStep]
    violation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "steps": [s.to_dict() for s in self.steps],
            "violation": self.violation,
        }
