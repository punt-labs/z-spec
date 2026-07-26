"""Type-check a Z spec with fuzz."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, Self, final

from punt_zspec.commands.result import CommandError, CommandFailure, CommandResult
from punt_zspec.fuzz import resolve_fuzz, run_fuzz
from punt_zspec.report import save_fuzz
from punt_zspec.types import FuzzResult


class FuzzResolver(Protocol):
    """Locate the fuzz binary, or return None when it is absent."""

    def __call__(self) -> Path | None: ...


class FuzzRunner(Protocol):
    """Run fuzz on a spec and return its structured result."""

    def __call__(self, spec: Path, binary: Path, /) -> FuzzResult: ...


class FuzzPersister(Protocol):
    """Persist a fuzz result alongside its spec and return the written path."""

    def __call__(self, spec: Path, result: FuzzResult, /) -> Path: ...


@final
class CheckCommand:
    """Resolve fuzz, type-check a spec, and persist the result."""

    _resolve: FuzzResolver
    _run: FuzzRunner
    _persist: FuzzPersister
    __slots__ = ("_persist", "_resolve", "_run")

    def __new__(
        cls,
        resolve: FuzzResolver = resolve_fuzz,
        run: FuzzRunner = run_fuzz,
        persist: FuzzPersister = save_fuzz,
    ) -> Self:
        self = super().__new__(cls)
        self._resolve = resolve
        self._run = run
        self._persist = persist
        return self

    def run(self, spec: Path) -> CommandResult[FuzzResult]:
        """Return the fuzz result, persisting it, or a typed failure."""
        if not spec.is_file():
            return CommandResult[FuzzResult].failed(
                CommandError(
                    CommandFailure.spec_not_found, f"Spec file not found: {spec}"
                )
            )
        binary = self._resolve()
        if binary is None:
            return CommandResult[FuzzResult].failed(
                CommandError(
                    CommandFailure.binary_missing,
                    "fuzz not found",
                    hint="Set $FUZZ or add fuzz to PATH.",
                )
            )
        result = self._run(spec, binary)
        self._persist(spec, result)
        return CommandResult.ok(result)
