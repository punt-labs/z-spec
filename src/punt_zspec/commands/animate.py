"""Animate a Z spec with probcli and persist the report."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, Self, final

from punt_zspec.commands.options import AnimateOptions
from punt_zspec.commands.result import CommandError, CommandFailure, CommandResult
from punt_zspec.prob import resolve_probcli, run_animate
from punt_zspec.report import save_report
from punt_zspec.types import ProbReport

_DEFAULT_OPTIONS = AnimateOptions()


class ProbResolver(Protocol):
    """Locate the probcli binary, or return None when it is absent."""

    # Path | None (PY-TS-14): None is a real state — probcli is not installed.
    def __call__(self) -> Path | None: ...


class AnimateRunner(Protocol):
    """Animate a spec and return the resulting report."""

    def __call__(
        self, spec: Path, binary: Path, /, *, steps: int, setsize: int
    ) -> ProbReport: ...


class ReportPersister(Protocol):
    """Persist a ProB report alongside its spec and return the written path."""

    def __call__(self, spec: Path, report: ProbReport, /) -> Path: ...


@final
class AnimateCommand:
    """Resolve probcli, animate a spec, and persist the report."""

    _resolve: ProbResolver
    _run: AnimateRunner
    _persist: ReportPersister
    __slots__ = ("_persist", "_resolve", "_run")

    def __new__(
        cls,
        resolve: ProbResolver = resolve_probcli,
        run: AnimateRunner = run_animate,
        persist: ReportPersister = save_report,
    ) -> Self:
        self = super().__new__(cls)
        self._resolve = resolve
        self._run = run
        self._persist = persist
        return self

    def run(
        self, spec: Path, options: AnimateOptions = _DEFAULT_OPTIONS
    ) -> CommandResult[ProbReport]:
        """Return the animation report, persisting it, or a typed failure."""
        if not spec.is_file():
            return CommandResult[ProbReport].failed(
                CommandError(
                    CommandFailure.spec_not_found, f"Spec file not found: {spec}"
                )
            )
        binary = self._resolve()
        if binary is None:
            return CommandResult[ProbReport].failed(
                CommandError(
                    CommandFailure.binary_missing,
                    "probcli not found",
                    hint="Set $PROBCLI or add probcli to PATH.",
                )
            )
        report = self._run(spec, binary, steps=options.steps, setsize=options.setsize)
        self._persist(spec, report)
        return CommandResult.ok(report)
