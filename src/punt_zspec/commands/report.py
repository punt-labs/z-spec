"""Load a previously saved ProB report."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, Self, final

from punt_zspec.commands.result import CommandError, CommandFailure, CommandResult
from punt_zspec.report import load_report
from punt_zspec.types import ProbReport


class ReportLoader(Protocol):
    """Load a saved report, or return None when none exists for the spec."""

    # ProbReport | None (PY-TS-14): absence is the documented contract —
    # a spec legitimately has no saved report yet.
    def __call__(self, spec: Path, /) -> ProbReport | None: ...


@final
class ReportCommand:
    """Return a spec's saved ProB report, or a report-missing failure."""

    _load: ReportLoader
    __slots__ = ("_load",)

    def __new__(cls, load: ReportLoader = load_report) -> Self:
        self = super().__new__(cls)
        self._load = load
        return self

    def run(self, spec: Path) -> CommandResult[ProbReport]:
        """Return the saved report, or a report-missing failure."""
        report = self._load(spec)
        if report is None:
            return CommandResult[ProbReport].failed(
                CommandError(
                    CommandFailure.report_missing,
                    f"No report found for {spec.name}",
                )
            )
        return CommandResult.ok(report)
