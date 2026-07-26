"""Test-coverage audit report and its constituent constraint types."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


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
