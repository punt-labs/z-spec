"""Result types for the fuzz Z type-checker."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class FuzzError:
    """A single fuzz type-checking error."""

    line: int
    column: int
    message: str


@dataclass(frozen=True)
class FuzzResult:
    """Result of running fuzz -t."""

    ok: bool
    errors: list[FuzzError] = field(default_factory=list)  # pyright: ignore[reportUnknownVariableType]
    raw_output: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "errors": [
                {"line": e.line, "column": e.column, "message": e.message}
                for e in self.errors
            ],
        }
