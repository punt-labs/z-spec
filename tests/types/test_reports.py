"""Tests for punt_zspec.types.reports."""

from __future__ import annotations

from punt_zspec.types import FuzzResult, SpecReports


def test_all_reports_absent_is_the_documented_contract() -> None:
    reports = SpecReports(report=None, fuzz=None, partition=None, audit=None)
    assert reports.fuzz is None


def test_populated_field_is_retained() -> None:
    fuzz = FuzzResult(ok=True)
    reports = SpecReports(report=None, fuzz=fuzz, partition=None, audit=None)
    assert reports.fuzz is fuzz
