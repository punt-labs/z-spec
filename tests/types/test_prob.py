"""Tests for punt_zspec.types.prob."""

from __future__ import annotations

from punt_zspec.types import (
    CheckResult,
    CheckStatus,
    CounterExample,
    OperationCoverage,
    ProbReport,
    TraceStep,
)


def _report(
    checks: list[CheckResult],
    counter_example: CounterExample | None = None,
) -> ProbReport:
    return ProbReport(
        timestamp="2026-01-01T00:00:00Z",
        probcli_version="1.13.1",
        setsize=1,
        checks=checks,
        operations=[OperationCoverage("Op", 3)],
        counter_example=counter_example,
        states_analysed=42,
        transitions_fired=150,
    )


def test_coverage_is_derived_from_the_fire_count() -> None:
    assert OperationCoverage("Op", 3).covered is True
    assert OperationCoverage("Op", 0).covered is False


def test_to_dict_carries_the_derived_coverage() -> None:
    assert OperationCoverage("Op", 0).to_dict() == {
        "name": "Op",
        "times_fired": 0,
        "covered": False,
    }


def test_ok_is_false_when_any_check_failed() -> None:
    report = _report([CheckResult("deadlock", CheckStatus.failed)])
    assert report.ok is False


def test_ok_is_true_for_skipped_and_passed() -> None:
    report = _report(
        [
            CheckResult("a", CheckStatus.passed),
            CheckResult("c", CheckStatus.skipped),
        ]
    )
    assert report.ok is True


def test_ok_is_false_when_a_check_only_warned() -> None:
    """A warning is an unestablished claim, and unestablished is not passing."""
    report = _report(
        [
            CheckResult("a", CheckStatus.passed),
            CheckResult("b", CheckStatus.warning, "not certified complete"),
        ]
    )
    assert report.ok is False


def test_to_dict_omits_counter_example_when_absent() -> None:
    report = _report([CheckResult("a", CheckStatus.passed)])
    assert "counter_example" not in report.to_dict()


def test_to_dict_nests_counter_example_when_present() -> None:
    example = CounterExample(
        steps=[TraceStep(1, "Op", {"x": "0"})], violation="inv broken"
    )
    report = _report([CheckResult("a", CheckStatus.failed)], example)
    assert report.to_dict()["counter_example"] == {
        "steps": [{"step_number": 1, "operation": "Op", "state": {"x": "0"}}],
        "violation": "inv broken",
    }
