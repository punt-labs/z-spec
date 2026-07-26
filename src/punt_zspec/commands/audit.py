"""Validate and persist an authored test-coverage audit report."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol, Self, final

from punt_zspec.commands.partition import SavedReport
from punt_zspec.commands.result import CommandError, CommandFailure, CommandResult
from punt_zspec.report import audit_from_dict, save_audit
from punt_zspec.types import AuditReport


class AuditParser(Protocol):
    """Validate a wire dict into an AuditReport, raising on bad shape."""

    # dict[str, Any] (PY-TS-14): JSON wire boundary — json.loads yields this.
    def __call__(self, data: dict[str, Any], /) -> AuditReport: ...


class AuditPersister(Protocol):
    """Persist an audit report beside its spec and return the written path."""

    def __call__(self, spec: Path, report: AuditReport, /) -> Path: ...


@final
class AuditCommand:
    """Parse an authored audit report and persist it beside the spec."""

    _parse: AuditParser
    _persist: AuditPersister
    __slots__ = ("_parse", "_persist")

    def __new__(
        cls,
        parse: AuditParser = audit_from_dict,
        persist: AuditPersister = save_audit,
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
                    f"Invalid audit report: {exc}",
                )
            )
        out = self._persist(spec, report)
        return CommandResult.ok(SavedReport(out))
