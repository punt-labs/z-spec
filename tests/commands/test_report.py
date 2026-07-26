"""Humble-object tests for ReportCommand — no disk I/O of real reports."""

from __future__ import annotations

from pathlib import Path

from punt_zspec.commands.report import ReportCommand
from punt_zspec.commands.result import CommandFailure
from punt_zspec.types import CheckResult, CheckStatus, ProbReport


def _sample_report() -> ProbReport:
    return ProbReport(
        timestamp="2020-01-01T00:00:00+00:00",
        probcli_version="1.0.0",
        setsize=2,
        checks=[CheckResult(name="init", status=CheckStatus.passed, detail="OK")],
        operations=[],
        counter_example=None,
        states_analysed=3,
        transitions_fired=4,
    )


def test_report_returns_loaded_report(spec: Path) -> None:
    report = _sample_report()
    cmd = ReportCommand(load=lambda _s: report)

    result = cmd.run(spec)

    assert result.is_ok
    assert result.unwrap() is report


def test_report_missing_returns_failure(spec: Path) -> None:
    cmd = ReportCommand(load=lambda _s: None)

    result = cmd.run(spec)

    assert not result.is_ok
    error = result.error
    assert error is not None
    assert error.kind is CommandFailure.report_missing
    expected = f'{{"ok": false, "error": "No report found for {spec.name}"}}'
    assert result.to_json() == expected


def test_report_missing_message_uses_spec_name(tmp_path: Path) -> None:
    spec = tmp_path / "nested" / "deep.tex"
    cmd = ReportCommand(load=lambda _s: None)

    result = cmd.run(spec)

    error = result.error
    assert error is not None
    assert error.message == "No report found for deep.tex"


def test_report_does_not_load_twice(spec: Path) -> None:
    calls: list[Path] = []

    def load(s: Path) -> ProbReport | None:
        calls.append(s)
        return _sample_report()

    ReportCommand(load=load).run(spec)

    assert calls == [spec]
