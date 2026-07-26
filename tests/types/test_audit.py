"""Tests for punt_zspec.types.audit."""

from __future__ import annotations

from punt_zspec.types import (
    AuditConfidence,
    AuditConstraint,
    AuditReport,
    AuditSuggestion,
)


def test_percentage_zero_total_returns_zero_not_zerodivision() -> None:
    report = AuditReport(
        specification="s",
        test_directory="d",
        timestamp="t",
        constraints=[],
        uncovered=[],
    )
    assert report.percentage == 0


def test_percentage_rounds_covered_ratio() -> None:
    covered = AuditConstraint("c1", "invariant", "S", covered_by="T.swift:1")
    uncovered = AuditSuggestion("c2", "invariant", "S", "add a test")
    report = AuditReport(
        specification="s",
        test_directory="d",
        timestamp="t",
        constraints=[covered],
        uncovered=[uncovered],
    )
    assert report.percentage == 50


def test_constraint_covered_is_false_without_covered_by() -> None:
    assert AuditConstraint("c", "invariant", "S").covered is False


def test_constraint_to_dict_omits_optional_keys_when_absent() -> None:
    result = AuditConstraint("c", "invariant", "S").to_dict()
    assert "coveredBy" not in result
    assert "confidence" not in result


def test_constraint_to_dict_includes_optional_keys_when_present() -> None:
    constraint = AuditConstraint(
        "c", "invariant", "S", covered_by="T.swift:9", confidence=AuditConfidence.high
    )
    result = constraint.to_dict()
    assert result["coveredBy"] == "T.swift:9"
    assert result["confidence"] == "high"


def test_suggestion_to_dict_omits_empty_test_pattern() -> None:
    assert "testPattern" not in AuditSuggestion("c", "inv", "S", "add").to_dict()


def test_suggestion_to_dict_includes_test_pattern_when_set() -> None:
    suggestion = AuditSuggestion("c", "inv", "S", "add", test_pattern="XCTAssert")
    assert suggestion.to_dict()["testPattern"] == "XCTAssert"
