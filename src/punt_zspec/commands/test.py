"""Run the full probcli suite and persist the report."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, Self, final

from punt_zspec.commands.options import ProbOptions
from punt_zspec.commands.result import CommandError, CommandFailure, CommandResult
from punt_zspec.prob import resolve_probcli, run_full_suite
from punt_zspec.report import save_report
from punt_zspec.types import ProbReport

_DEFAULT_OPTIONS = ProbOptions()


class ProbResolver(Protocol):
    """Locate the probcli binary, or return None when it is absent."""

    # Path | None (PY-TS-14): None is a real state — probcli is not installed.
    def __call__(self) -> Path | None: ...


class SuiteRunner(Protocol):
    """Run the full probcli suite and return the resulting report."""

    def __call__(
        self,
        spec: Path,
        binary: Path,
        /,
        *,
        setsize: int,
        max_ops: int,
        timeout_ms: int,
    ) -> ProbReport: ...


class ReportPersister(Protocol):
    """Persist a ProB report alongside its spec and return the written path."""

    def __call__(self, spec: Path, report: ProbReport, /) -> Path: ...


@final
class TestCommand:
    """Resolve probcli, run the full suite, and persist the report."""

    # The name matches pytest's Test* collection pattern; this is a domain
    # command, not a test case, so opt out of collection.
    __test__ = False

    _resolve: ProbResolver
    _run: SuiteRunner
    _persist: ReportPersister
    __slots__ = ("_persist", "_resolve", "_run")

    def __new__(
        cls,
        resolve: ProbResolver = resolve_probcli,
        run: SuiteRunner = run_full_suite,
        persist: ReportPersister = save_report,
    ) -> Self:
        self = super().__new__(cls)
        self._resolve = resolve
        self._run = run
        self._persist = persist
        return self

    def run(
        self, spec: Path, options: ProbOptions = _DEFAULT_OPTIONS
    ) -> CommandResult[ProbReport]:
        """Return the suite report, persisting it, or a typed failure."""
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
        report = self._run(
            spec,
            binary,
            setsize=options.setsize,
            max_ops=options.max_ops,
            timeout_ms=options.timeout_ms,
        )
        self._persist(spec, report)
        return CommandResult.ok(report)
