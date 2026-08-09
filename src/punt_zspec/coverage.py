"""probcli's operation census: which operations fired, and how often.

The census is the answer to one question — which operations a run exercised —
and it is read separately from the verdict on the run itself, because the two
claims survive a truncated exploration differently. Coverage is existential:
more exploration only ever adds covered operations, so a clean census from a
run that stopped short is still sound.
"""

from __future__ import annotations

import re
from itertools import takewhile
from typing import Protocol, Self, final

from punt_zspec.types import CheckResult, CheckStatus, OperationCoverage

# The census probcli prints under "Coverage:" when -coverage is passed. One
# bracketed line: state totals, then COVERED_OPERATIONS (n) and
# UNCOVERED_OPERATIONS (m), each headline followed by exactly the number of
# comma-separated entries it declares.
_CENSUS_RE = re.compile(r"\[STATES \(\d+\),[^\]]*\]")
_HEADLINE_RE = re.compile(r"(?:UN)?COVERED_OPERATIONS \(\d+\)")

_COVERED = "COVERED_OPERATIONS"
_UNCOVERED = "UNCOVERED_OPERATIONS"
_CHECK_NAME = "coverage"


class Coverage(Protocol):
    """What one probcli run knows about which operations fired."""

    @property
    def operations(self) -> tuple[OperationCoverage, ...]:
        """Return every operation the run accounted for, with its fire count."""
        ...

    def check(self) -> CheckResult:
        """Return the coverage verdict as a named check result."""
        ...


@final
class UnreadableCoverage:
    """A run whose coverage question went unanswered.

    Either probcli printed no census — the run did not ask — or it printed one
    that will not parse. Both report a failed check, because unanswered is not
    covered: a run that never asked must not be mistaken for one that asked and
    got a clean answer.
    """

    _reason: str
    __slots__ = ("_reason",)

    def __new__(cls, reason: str) -> Self:
        self = super().__new__(cls)
        self._reason = reason
        return self

    @property
    def operations(self) -> tuple[OperationCoverage, ...]:
        """Return no operations — nothing was measured."""
        return ()

    def check(self) -> CheckResult:
        """Return a failed check naming why the census could not be read."""
        return CheckResult(
            name=_CHECK_NAME, status=CheckStatus.failed, detail=self._reason
        )


@final
class CoverageCensus:
    """probcli's operation census: the operations it named, with fire counts.

    An operation appears once, whether it fired or not; ``covered`` is derived
    from the count, so a covered operation that never fired cannot be built.
    """

    _operations: tuple[OperationCoverage, ...]
    __slots__ = ("_operations",)

    def __new__(cls, operations: tuple[OperationCoverage, ...]) -> Self:
        self = super().__new__(cls)
        self._operations = operations
        return self

    @classmethod
    def locate(cls, text: str) -> Coverage:
        """Return the census in one run's output, or why there is none to read."""
        found = _CENSUS_RE.search(text)
        if found is None:
            # State only what was observed. A run can lack a census because it
            # was never asked, or because it died before printing one, and the
            # census cannot tell which — the check that classifies the run
            # carries the cause on its own line.
            return UnreadableCoverage("probcli printed no coverage census")
        return cls.read(found.group(0))

    @classmethod
    def read(cls, census: str) -> Coverage:
        """Return the census parsed from probcli's bracketed coverage line."""
        tokens = census.removeprefix("[").removesuffix("]").split(",")
        try:
            fired = tuple(cls._entry(t) for t in cls._section(tokens, _COVERED))
            idle = tuple(
                OperationCoverage(name=name, times_fired=0)
                for name in cls._section(tokens, _UNCOVERED)
            )
        except ValueError as exc:
            return UnreadableCoverage(str(exc))
        return cls(fired + idle)

    @staticmethod
    def _section(tokens: list[str], headline: str) -> list[str]:
        """Return a headline's entries, checked against the length it declares.

        A headline declaring more entries than it lists means the line was
        truncated or the format moved; either way the census is unreadable, and
        a short list must never be read as full coverage.
        """
        for index, token in enumerate(tokens):
            declared = re.fullmatch(rf"{headline} \((\d+)\)", token)
            if declared is None:
                continue
            entries = list(
                takewhile(lambda t: not _HEADLINE_RE.fullmatch(t), tokens[index + 1 :])
            )
            if len(entries) != int(declared.group(1)):
                msg = (
                    f"{headline} declares {declared.group(1)} entries "
                    f"but lists {len(entries)}"
                )
                raise ValueError(msg)
            return entries
        msg = f"probcli's coverage census has no {headline}"
        raise ValueError(msg)

    @staticmethod
    def _entry(token: str) -> OperationCoverage:
        """Return one ``Name:count`` census entry as an OperationCoverage."""
        name, separator, count = token.partition(":")
        if not separator or not count.isdigit():
            msg = f"unreadable coverage entry: {token}"
            raise ValueError(msg)
        return OperationCoverage(name=name, times_fired=int(count))

    @property
    def operations(self) -> tuple[OperationCoverage, ...]:
        """Return every operation probcli named, with its fire count."""
        return self._operations

    @property
    def uncovered(self) -> tuple[str, ...]:
        """Return the names of the operations that never fired."""
        return tuple(op.name for op in self._operations if not op.covered)

    def check(self) -> CheckResult:
        """Return the coverage verdict — an uncovered operation is dead spec."""
        idle = self.uncovered
        if idle:
            return CheckResult(
                name=_CHECK_NAME,
                status=CheckStatus.failed,
                detail=f"never fired: {', '.join(idle)}",
            )
        return CheckResult(
            name=_CHECK_NAME,
            status=CheckStatus.passed,
            detail=f"{len(self._operations)} operations covered",
        )
