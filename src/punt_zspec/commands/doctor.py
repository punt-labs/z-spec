"""Report Z-toolkit environment health."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, Self, final

from punt_zspec import __version__
from punt_zspec.commands.result import CommandFailure, CommandResult
from punt_zspec.fuzz import resolve_fuzz
from punt_zspec.prob import resolve_probcli


class BinaryResolver(Protocol):
    """Locate a toolchain binary, or return None when it is absent."""

    # Path | None (PY-TS-14): None is a real state — the binary is not installed.
    def __call__(self) -> Path | None:
        """Return the binary's path, or None when it is not installed."""
        ...


@final
@dataclass(frozen=True, slots=True)
class DoctorReport:
    """Resolved toolchain health, including any missing binaries."""

    version: str
    fuzz: Path | None  # PY-TS-14: None = "fuzz not installed", a real state
    probcli: Path | None  # PY-TS-14: None = "probcli not installed", a real state

    @property
    def healthy(self) -> bool:
        """Whether both fuzz and probcli resolved."""
        return self.fuzz is not None and self.probcli is not None

    def to_dict(self) -> dict[str, Any]:  # PY-TS-14: JSON wire boundary
        """Return the wire form of this report."""
        return {
            "version": self.version,
            "fuzz": str(self.fuzz) if self.fuzz else None,
            "probcli": str(self.probcli) if self.probcli else None,
            "healthy": self.healthy,
        }


@final
class DoctorCommand:
    """Resolve both binaries and report toolchain health."""

    _resolve_fuzz: BinaryResolver
    _resolve_probcli: BinaryResolver
    __slots__ = ("_resolve_fuzz", "_resolve_probcli")

    def __new__(
        cls,
        fuzz: BinaryResolver = resolve_fuzz,
        probcli: BinaryResolver = resolve_probcli,
    ) -> Self:
        """Inject the binary resolvers; the defaults search the real toolchain."""
        self = super().__new__(cls)
        self._resolve_fuzz = fuzz
        self._resolve_probcli = probcli
        return self

    def run(self) -> CommandResult[DoctorReport]:
        """Return a health report even when a binary is missing."""
        report = DoctorReport(
            version=__version__,
            fuzz=self._resolve_fuzz(),
            probcli=self._resolve_probcli(),
        )
        return CommandResult.completed(
            report, failure=None if report.healthy else CommandFailure.binary_missing
        )
