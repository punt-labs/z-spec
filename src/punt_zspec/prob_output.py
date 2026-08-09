"""One probcli run — its text and exit status — and the facts that text asserts.

Everything here reads what probcli said. Nothing infers what probcli did not
say: an operation is covered because the census counted it firing, and a run
that was never asked for a census reports that it does not know.
"""

from __future__ import annotations

import re
import subprocess
from itertools import takewhile
from typing import ClassVar, Protocol, Self, final

from punt_zspec.types import (
    CheckResult,
    CheckStatus,
    CounterExample,
    OperationCoverage,
    TraceStep,
)

_STATES_RE = re.compile(r"States\s+analysed:\s*(\d+)")
_TRANS_RE = re.compile(r"Transitions\s+fired:\s*(\d+)")
_OP_RE = re.compile(r"Z operation:\s*(\w+)")
_VERSION_RE = re.compile(r"ProB CLI.*?(\d+\.\d+\.\d+)")
_COUNTER_RE = re.compile(r"(?<!No )COUNTER\s*EXAMPLE\s*FOUND", re.IGNORECASE)
_STEP_RE = re.compile(r"(\d+):\s*(\w+)")

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


@final
class ProbOutput:
    """The combined stdout, stderr, and exit status of one probcli run."""

    _text: str
    _returncode: int
    __slots__ = ("_returncode", "_text")

    # Success markers probcli prints for the checks that do not explore a state
    # space. Ordered: the first marker present decides.
    #
    # ALL OPERATIONS COVERED is deliberately absent. It answers the coverage
    # question, not "did this run find anything", and probcli prints it mid-run
    # — before it goes on to find a counter-example. Reading it as a run verdict
    # passes a deadlocking specification.
    _MARKERS: ClassVar[tuple[tuple[str, CheckStatus, str], ...]] = (
        ("no deadlock", CheckStatus.passed, "deadlock-free"),
        ("no assertion", CheckStatus.skipped, "no assertions defined"),
    )

    def __new__(cls, text: str, returncode: int) -> Self:
        self = super().__new__(cls)
        self._text = text
        self._returncode = returncode
        return self

    @classmethod
    def of(cls, completed: subprocess.CompletedProcess[str]) -> Self:
        """Return the output of a finished probcli process."""
        return cls(completed.stdout + completed.stderr, completed.returncode)

    @property
    def text(self) -> str:
        """Return the run's combined output verbatim."""
        return self._text

    @property
    def version(self) -> str:
        """Return the probcli version the run announced, or ``unknown``."""
        found = _VERSION_RE.search(self._text)
        return found.group(1) if found else "unknown"

    @property
    def states_analysed(self) -> int:
        """Return the state count probcli reported, or zero if it reported none."""
        found = _STATES_RE.search(self._text)
        return int(found.group(1)) if found else 0

    @property
    def transitions_fired(self) -> int:
        """Return the transition count probcli reported, or zero if it reported none."""
        found = _TRANS_RE.search(self._text)
        return int(found.group(1)) if found else 0

    @property
    def declared_operations(self) -> tuple[str, ...]:
        """Return the Z operation names probcli echoed as it loaded the spec."""
        return tuple(_OP_RE.findall(self._text))

    def coverage(self) -> Coverage:
        """Return the operation census this run printed, or why it cannot be read."""
        census = _CENSUS_RE.search(self._text)
        if census is None:
            return UnreadableCoverage(
                "probcli printed no coverage census — the run did not pass -coverage"
            )
        return CoverageCensus.read(census.group(0))

    # CounterExample | None (PY-TS-14): absence is the contract — a clean run
    # has no counter-example, and that is the answer, not a failure to produce
    # one.
    def counter_example(self) -> CounterExample | None:
        """Return the counter-example trace probcli printed, if it printed one."""
        if not _COUNTER_RE.search(self._text):
            return None
        steps: list[TraceStep] = []
        violation = ""
        for line in self._trailing_lines():
            step = _STEP_RE.match(line)
            if step is not None:
                steps.append(
                    TraceStep(
                        step_number=int(step.group(1)),
                        operation=step.group(2),
                        state={},
                    )
                )
            elif not violation:
                violation = line
        return CounterExample(steps=steps, violation=violation) if steps else None

    def _trailing_lines(self) -> list[str]:
        """Return the non-empty lines following the counter-example announcement.

        Called only once ``counter_example`` has seen the announcement, so the
        search for it is known to succeed.
        """
        lines = self._text.split("\n")
        opening = next(i for i, line in enumerate(lines) if _COUNTER_RE.search(line))
        return [
            stripped
            for line in lines[opening + 1 :]
            if (stripped := line.strip()) and not _COUNTER_RE.search(line)
        ]

    def check(self, name: str) -> CheckResult:
        """Return this run classified as the named check.

        A counter-example is tested first and unconditionally. probcli prints
        its success markers as it goes and only then reports what it found, so
        any marker consulted ahead of the counter-example can mask one.
        """
        lowered = self._text.lower()
        if _COUNTER_RE.search(self._text):
            return CheckResult(name, CheckStatus.failed, self._violation())
        if "no counter example found" in lowered or "no counter-example" in lowered:
            return CheckResult(name, CheckStatus.passed, self._exploration_detail())
        for marker, status, detail in self._MARKERS:
            if marker in lowered:
                return CheckResult(name, status, detail)
        return self._exit_verdict(name, lowered)

    def _violation(self) -> str:
        """Return the violation probcli named, falling back to its leading output."""
        found = self.counter_example()
        if found is None or not found.violation:
            return self._excerpt()
        return found.violation

    def _exit_verdict(self, name: str, lowered: str) -> CheckResult:
        """Return the verdict for output carrying no recognised probcli marker."""
        if self._returncode == 0:
            return CheckResult(name, CheckStatus.passed, "OK")
        if "not all transitions" in lowered:
            return CheckResult(name, CheckStatus.warning, "incomplete exploration")
        return CheckResult(name, CheckStatus.failed, self._excerpt())

    def _exploration_detail(self) -> str:
        """Return the states-and-transitions summary of a clean exploration."""
        counted = [
            f"{value} {noun}"
            for value, noun in (
                (self.states_analysed, "states"),
                (self.transitions_fired, "transitions"),
            )
            if value
        ]
        return ", ".join(counted) or "OK"

    def _excerpt(self) -> str:
        """Return the leading output, trimmed to fit a check's detail line."""
        return self._text.strip()[:200]
