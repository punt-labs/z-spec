"""Validate and persist an authored TTF partition report."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, Self, final

from punt_zspec.commands.result import CommandError, CommandFailure, CommandResult
from punt_zspec.report import partition_from_dict, save_partition
from punt_zspec.types import PartitionReport


@final
@dataclass(frozen=True, slots=True)
class SavedReport:
    """The written path of a persisted report — shared by partition and audit."""

    path: Path

    def to_dict(self) -> dict[str, Any]:  # PY-TS-14: JSON wire boundary
        return {"ok": True, "path": str(self.path)}


class PartitionParser(Protocol):
    """Validate a wire dict into a PartitionReport, raising on bad shape."""

    # dict[str, Any] (PY-TS-14): JSON wire boundary — json.loads yields this.
    def __call__(self, data: dict[str, Any], /) -> PartitionReport: ...


class PartitionPersister(Protocol):
    """Persist a partition report beside its spec and return the written path."""

    def __call__(self, spec: Path, report: PartitionReport, /) -> Path: ...


@final
class PartitionCommand:
    """Parse an authored partition report and persist it beside the spec."""

    _parse: PartitionParser
    _persist: PartitionPersister
    __slots__ = ("_parse", "_persist")

    def __new__(
        cls,
        parse: PartitionParser = partition_from_dict,
        persist: PartitionPersister = save_partition,
    ) -> Self:
        self = super().__new__(cls)
        self._parse = parse
        self._persist = persist
        return self

    def run(self, spec: Path, report_json: str) -> CommandResult[SavedReport]:
        """Return the saved path, or a typed failure."""
        if not spec.is_file():
            return CommandResult[SavedReport].failed(
                CommandError(
                    CommandFailure.spec_not_found, f"Spec file not found: {spec}"
                )
            )
        try:  # PY-EH-5 exception: json + wire-schema decode is an I/O boundary
            report = self._parse(json.loads(report_json))
        except (
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
            AttributeError,
        ) as exc:
            return CommandResult[SavedReport].failed(
                CommandError(
                    CommandFailure.invalid_report,
                    f"Invalid partition report: {exc}",
                )
            )
        out = self._persist(spec, report)
        return CommandResult.ok(SavedReport(out))
