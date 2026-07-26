"""Humble-object tests for AuditCommand — injected parse/persist, no I/O."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from punt_zspec.commands.audit import AuditCommand
from punt_zspec.commands.partition import SavedReport
from punt_zspec.commands.result import CommandFailure
from punt_zspec.types import AuditReport

_EMPTY_REPORT = AuditReport(
    specification="s",
    test_directory="",
    timestamp="",
    constraints=[],
    uncovered=[],
)


def _unreachable_parse(_data: dict[str, Any]) -> AuditReport:
    pytest.fail("parser must not be called")


def _unreachable_persist(_spec: Path, _report: AuditReport) -> Path:
    pytest.fail("persister must not be called")


def test_audit_persists_and_returns_ok(spec: Path) -> None:
    saved: list[tuple[Path, AuditReport]] = []

    def persist(s: Path, r: AuditReport) -> Path:
        saved.append((s, r))
        return s.parent / "s.audit.json"

    cmd = AuditCommand(parse=lambda _d: _EMPTY_REPORT, persist=persist)

    result = cmd.run(spec, json.dumps({"constraints": []}))

    assert result.is_ok
    assert result.unwrap() == SavedReport(spec.parent / "s.audit.json")
    assert saved == [(spec, _EMPTY_REPORT)]


def test_audit_spec_not_found(tmp_path: Path) -> None:
    missing = tmp_path / "nope.tex"
    cmd = AuditCommand(parse=_unreachable_parse, persist=_unreachable_persist)

    result = cmd.run(missing, "{}")

    assert not result.is_ok
    error = result.error
    assert error is not None
    assert error.kind is CommandFailure.spec_not_found


def test_audit_invalid_json(spec: Path) -> None:
    cmd = AuditCommand(parse=_unreachable_parse, persist=_unreachable_persist)

    result = cmd.run(spec, "{bad}")

    assert not result.is_ok
    error = result.error
    assert error is not None
    assert error.kind is CommandFailure.invalid_report
    assert "Invalid audit report" in error.message


def test_audit_invalid_schema(spec: Path) -> None:
    def parse(_data: dict[str, Any]) -> AuditReport:
        raise KeyError("constraints")

    cmd = AuditCommand(parse=parse, persist=_unreachable_persist)

    result = cmd.run(spec, "{}")

    assert not result.is_ok
    error = result.error
    assert error is not None
    assert error.kind is CommandFailure.invalid_report
