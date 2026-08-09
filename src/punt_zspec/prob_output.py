"""One probcli run — its text and exit status — and the facts that text asserts.

Everything here reads what probcli said. Nothing infers what probcli did not
say: an operation is covered because the census counted it firing, and a run
that was never asked for a census reports that it does not know.
"""

from __future__ import annotations

import re
import subprocess
from typing import ClassVar, Self, final

from punt_zspec.coverage import Coverage, CoverageCensus
from punt_zspec.types import CheckResult, CheckStatus, CounterExample, TraceStep

_STATES_RE = re.compile(r"States\s+analysed:\s*(\d+)")
_TRANS_RE = re.compile(r"Transitions\s+fired:\s*(\d+)")
_OP_RE = re.compile(r"Z operation:\s*(\w+)")
_VERSION_RE = re.compile(r"ProB CLI.*?(\d+\.\d+\.\d+)")
_COUNTER_RE = re.compile(r"(?<!No )COUNTER\s*EXAMPLE\s*FOUND", re.IGNORECASE)
_STEP_RE = re.compile(r"(\d+):\s*(\w+)")

# probcli's own tag for a run that stopped short of enumerating every
# transition. It prints this beside "No counter example found", so the two
# arrive together and the first phrase read decides the verdict.
_INCOMPLETE_RE = re.compile(r"model_check_incomplete")
_BOUND_RE = re.compile(r"(MAX_OPERATIONS=\d+) was too small")

# probcli's own error tally, printed only when something went wrong and absent
# from a clean run. It is the general failure signal every check can read: the
# -init step in particular emits no counter-example, no census and none of the
# markers, so without this its verdict would rest on an exit status probcli
# does not set — it exits 0 even on INITIALISATION FAILS.
_ERRORS_RE = re.compile(r"Total Errors:\s*(\d+)")
_ERROR_TAG_RE = re.compile(r"\*\*\* error occurred \*\*\*\s*\n!\s*(\w+)")


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
        return CoverageCensus.locate(self._text)

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
        any marker consulted ahead of the counter-example can mask one. A
        counter-example survives a truncated run — finding one is an existential
        claim — so it outranks incompleteness.

        Incompleteness is tested next, ahead of "no counter example found",
        because probcli prints both on the same line and the absence of a
        counter-example is a *universal* claim over the reachable states. A run
        that stopped short cannot establish it.
        """
        lowered = self._text.lower()
        if _COUNTER_RE.search(self._text):
            return CheckResult(name, CheckStatus.failed, self._violation())
        if self._error_count():
            return CheckResult(name, CheckStatus.failed, self._reported_errors())
        if _INCOMPLETE_RE.search(self._text):
            return CheckResult(name, CheckStatus.warning, self._uncertified())
        if "no counter example found" in lowered or "no counter-example" in lowered:
            return CheckResult(name, CheckStatus.passed, self._exploration_detail())
        for marker, status, detail in self._MARKERS:
            if marker in lowered:
                return CheckResult(name, status, detail)
        return self._exit_verdict(name)

    def _error_count(self) -> int:
        """Return how many errors probcli tallied, or zero if it tallied none."""
        found = _ERRORS_RE.search(self._text)
        return int(found.group(1)) if found else 0

    def _reported_errors(self) -> str:
        """Return probcli's error count and the sources it named for them."""
        tags = sorted(set(_ERROR_TAG_RE.findall(self._text)))
        named = f": {', '.join(tags)}" if tags else ""
        return f"probcli reported {self._error_count()} error(s){named}"

    def _uncertified(self) -> str:
        """Return why probcli could not certify it explored every transition."""
        bound = _BOUND_RE.search(self._text)
        raise_it = f"; raise {bound.group(1).split('=')[0]}" if bound else ""
        return f"{self._exploration_detail()}, not certified complete{raise_it}"

    def _violation(self) -> str:
        """Return the violation probcli named, falling back to its leading output."""
        found = self.counter_example()
        if found is None or not found.violation:
            return self._excerpt()
        return found.violation

    def _exit_verdict(self, name: str) -> CheckResult:
        """Return the verdict when probcli's output asserted nothing either way.

        The exit status is the last resort, and a weak one — probcli exits 0 on
        a counter-example, on INITIALISATION FAILS, and on an incompleteness
        warning alike. It is consulted only once the output has been searched
        for a counter-example, for probcli's own error tally, for an
        incompleteness warning, and for every success marker, so what reaches
        here is a run that reported nothing at all. Anything probcli does say
        is read before this point.
        """
        if self._returncode == 0:
            return CheckResult(name, CheckStatus.passed, "OK")
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
