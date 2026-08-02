"""Humble-object tests for CheckCommand — no fuzz, no subprocess."""

from __future__ import annotations

from pathlib import Path

import pytest

from punt_zspec.commands.check import CheckCommand
from punt_zspec.commands.result import CommandFailure
from punt_zspec.types import FuzzError, FuzzResult


def _present() -> Path | None:
    return Path("/fake/fuzz")


def _unreachable_resolve() -> Path | None:
    pytest.fail("resolver must not be called")


def _unreachable_run(_spec: Path, _binary: Path) -> FuzzResult:
    pytest.fail("runner must not be called")


def _unreachable_persist(_spec: Path, _result: FuzzResult) -> Path:
    pytest.fail("persister must not be called")


def test_check_persists_and_returns_ok(spec: Path) -> None:
    saved: list[tuple[Path, FuzzResult]] = []

    def persist(s: Path, r: FuzzResult) -> Path:
        saved.append((s, r))
        return s

    cmd = CheckCommand(
        resolve=_present,
        run=lambda _s, _b: FuzzResult(ok=True),
        persist=persist,
    )

    result = cmd.run(spec)

    assert result.is_ok
    assert result.unwrap().ok
    assert saved == [(spec, FuzzResult(ok=True))]


def test_check_persists_even_when_fuzz_reports_errors(spec: Path) -> None:
    fuzz = FuzzResult(ok=False, errors=[FuzzError(line=10, column=3, message="bad")])
    saved: list[tuple[Path, FuzzResult]] = []

    def persist(s: Path, r: FuzzResult) -> Path:
        saved.append((s, r))
        return s

    cmd = CheckCommand(resolve=_present, run=lambda _s, _b: fuzz, persist=persist)

    result = cmd.run(spec)

    assert result.is_ok
    assert not result.unwrap().ok
    assert saved == [(spec, fuzz)]


def test_check_binary_missing_returns_mcp_wire_failure(spec: Path) -> None:
    cmd = CheckCommand(
        resolve=lambda: None,
        run=_unreachable_run,
        persist=_unreachable_persist,
    )

    result = cmd.run(spec)

    assert not result.is_ok
    error = result.error
    assert error is not None
    assert error.kind is CommandFailure.binary_missing
    assert result.to_json() == (
        '{"ok": false, "error": "fuzz not found", '
        '"hint": "Set $FUZZ or add fuzz to PATH."}'
    )


def test_check_spec_not_found_returns_failure(tmp_path: Path) -> None:
    missing = tmp_path / "nope.tex"
    cmd = CheckCommand(
        resolve=_unreachable_resolve,
        run=_unreachable_run,
        persist=_unreachable_persist,
    )

    result = cmd.run(missing)

    assert not result.is_ok
    error = result.error
    assert error is not None
    assert error.kind is CommandFailure.spec_not_found
    expected = f'{{"ok": false, "error": "Spec file not found: {missing}"}}'
    assert result.to_json() == expected
