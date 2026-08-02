"""Humble-object tests for TestCommand — no probcli, no subprocess."""

from __future__ import annotations

from pathlib import Path

import pytest

from punt_zspec.commands.options import ProbOptions
from punt_zspec.commands.result import CommandFailure
from punt_zspec.commands.test import TestCommand
from punt_zspec.types import ProbReport


def _report() -> ProbReport:
    return ProbReport(
        timestamp="2020-01-01T00:00:00+00:00",
        probcli_version="1.0.0",
        setsize=2,
        checks=[],
        operations=[],
        counter_example=None,
        states_analysed=0,
        transitions_fired=0,
    )


def _present() -> Path | None:
    return Path("/bin/probcli")


def _unreachable_resolve() -> Path | None:
    pytest.fail("resolver must not be called")


def _unreachable_run(
    _spec: Path, _binary: Path, /, *, setsize: int, max_ops: int, timeout_ms: int
) -> ProbReport:
    pytest.fail("runner must not be called")


def _unreachable_persist(_spec: Path, _report: ProbReport, /) -> Path:
    pytest.fail("persister must not be called")


def test_test_persists_and_threads_options(spec: Path) -> None:
    report = _report()
    seen: dict[str, int] = {}
    saved: list[tuple[Path, ProbReport]] = []

    def run(
        _s: Path, _b: Path, /, *, setsize: int, max_ops: int, timeout_ms: int
    ) -> ProbReport:
        seen.update(setsize=setsize, max_ops=max_ops, timeout_ms=timeout_ms)
        return report

    def persist(s: Path, r: ProbReport, /) -> Path:
        saved.append((s, r))
        return s

    cmd = TestCommand(resolve=_present, run=run, persist=persist)

    result = cmd.run(spec, ProbOptions(setsize=5, max_ops=42, timeout_ms=9000))

    assert result.is_ok
    assert result.unwrap() is report
    assert seen == {"setsize": 5, "max_ops": 42, "timeout_ms": 9000}
    assert saved == [(spec, report)]


def test_test_binary_missing_returns_wire_failure(spec: Path) -> None:
    cmd = TestCommand(
        resolve=lambda: None, run=_unreachable_run, persist=_unreachable_persist
    )

    result = cmd.run(spec)

    assert not result.is_ok
    error = result.error
    assert error is not None
    assert error.kind is CommandFailure.binary_missing
    assert result.to_json() == (
        '{"ok": false, "error": "probcli not found", '
        '"hint": "Set $PROBCLI or add probcli to PATH."}'
    )


def test_test_spec_not_found_returns_failure(tmp_path: Path) -> None:
    missing = tmp_path / "nope.tex"
    cmd = TestCommand(
        resolve=_unreachable_resolve,
        run=_unreachable_run,
        persist=_unreachable_persist,
    )

    result = cmd.run(missing)

    assert not result.is_ok
    error = result.error
    assert error is not None
    assert error.kind is CommandFailure.spec_not_found


def test_test_uses_default_options(spec: Path) -> None:
    seen: dict[str, int] = {}

    def run(
        _s: Path, _b: Path, /, *, setsize: int, max_ops: int, timeout_ms: int
    ) -> ProbReport:
        seen.update(setsize=setsize, max_ops=max_ops, timeout_ms=timeout_ms)
        return _report()

    TestCommand(resolve=_present, run=run, persist=lambda s, _r: s).run(spec)

    assert seen == {"setsize": 2, "max_ops": 1000, "timeout_ms": 30000}
