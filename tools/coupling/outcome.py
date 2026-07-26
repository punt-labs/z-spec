"""The result of a coupling ratchet operation: an exit code plus report lines."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Self


@dataclass(frozen=True, slots=True)
class Outcome:
    """An exit code paired with the lines to print for a ratchet operation."""

    exit_code: int
    lines: tuple[str, ...]

    @classmethod
    def passed(cls, *lines: str) -> Self:
        """Return a success outcome carrying the given report lines."""
        return cls(0, lines)

    @classmethod
    def failed(cls, *lines: str) -> Self:
        """Return a failure outcome carrying the given report lines."""
        return cls(1, lines)
