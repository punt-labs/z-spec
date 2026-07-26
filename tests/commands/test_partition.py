"""Humble-object tests for PartitionCommand — injected parse/persist, no I/O."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from punt_zspec.commands.partition import PartitionCommand, SavedReport
from punt_zspec.commands.result import CommandFailure
from punt_zspec.types import PartitionReport

_EMPTY_REPORT = PartitionReport(specification="s", timestamp="", operations=[])


def _unreachable_parse(_data: dict[str, Any]) -> PartitionReport:
    pytest.fail("parser must not be called")


def _unreachable_persist(_spec: Path, _report: PartitionReport) -> Path:
    pytest.fail("persister must not be called")


def test_partition_persists_and_returns_ok(spec: Path) -> None:
    saved: list[tuple[Path, PartitionReport]] = []

    def persist(s: Path, r: PartitionReport) -> Path:
        saved.append((s, r))
        return s.parent / "s.partition.json"

    cmd = PartitionCommand(parse=lambda _d: _EMPTY_REPORT, persist=persist)

    result = cmd.run(spec, json.dumps({"operations": []}))

    assert result.is_ok
    assert result.unwrap() == SavedReport(spec.parent / "s.partition.json")
    assert saved == [(spec, _EMPTY_REPORT)]


def test_partition_ok_wire_format(spec: Path) -> None:
    out = spec.parent / "s.partition.json"
    cmd = PartitionCommand(parse=lambda _d: _EMPTY_REPORT, persist=lambda _s, _r: out)

    result = cmd.run(spec, "{}")

    assert result.to_json() == f'{{"ok": true, "path": "{out}"}}'


def test_partition_spec_not_found(tmp_path: Path) -> None:
    missing = tmp_path / "nope.tex"
    cmd = PartitionCommand(parse=_unreachable_parse, persist=_unreachable_persist)

    result = cmd.run(missing, "{}")

    assert not result.is_ok
    error = result.error
    assert error is not None
    assert error.kind is CommandFailure.spec_not_found
    expected = f'{{"ok": false, "error": "Spec file not found: {missing}"}}'
    assert result.to_json() == expected


def test_partition_invalid_json(spec: Path) -> None:
    cmd = PartitionCommand(parse=_unreachable_parse, persist=_unreachable_persist)

    result = cmd.run(spec, "not json")

    assert not result.is_ok
    error = result.error
    assert error is not None
    assert error.kind is CommandFailure.invalid_report
    assert "Invalid partition report" in error.message


def test_partition_invalid_schema(spec: Path) -> None:
    def parse(_data: dict[str, Any]) -> PartitionReport:
        raise KeyError("operations")

    cmd = PartitionCommand(parse=parse, persist=_unreachable_persist)

    result = cmd.run(spec, "{}")

    assert not result.is_ok
    error = result.error
    assert error is not None
    assert error.kind is CommandFailure.invalid_report


@pytest.mark.parametrize("payload", ["[]", "null", '"x"', "3"])
def test_partition_non_dict_json_is_invalid(spec: Path, payload: str) -> None:
    # The real parser calls .get() on the parsed value; a non-dict raises
    # AttributeError, which the command must classify as invalid_report.
    cmd = PartitionCommand(persist=_unreachable_persist)

    result = cmd.run(spec, payload)

    assert not result.is_ok
    error = result.error
    assert error is not None
    assert error.kind is CommandFailure.invalid_report
    assert "Invalid partition report" in error.message
