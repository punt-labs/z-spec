"""Per-file and whole-change verdicts for a ratchet check."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Self

from .thresholds import Thresholds


@dataclass(frozen=True, slots=True)
class Row:
    """One metric comparison line in the check report."""

    file: str
    metric: str
    baseline: str
    current: str
    delta: str
    status: str

    def render(self) -> str:
        """Return the row formatted for the comparison table."""
        return (
            f"{self.file:<40} {self.metric:<26} {self.baseline:>10} "
            f"{self.current:>10} {self.delta:>8} {self.status:>10}"
        )


class FileReview:
    """Compare one touched file's current metrics against its base baseline.

    The base entry already accounts for renames (S8): a rename target is
    handed its predecessor's baseline, so its history cannot be laundered.
    A regression is *waived* only when the in-tree baseline has locked the
    current value (S4) and the audit log records a matching relaxation (S7).
    """

    _path: str
    _base_present: bool
    _rows: tuple[Row, ...]
    _regressed: tuple[str, ...]
    _waived: tuple[str, ...]
    _improved: bool
    _new_passes: bool

    def __new__(
        cls,
        path: str,
        current: dict[str, float],
        base: dict[str, float] | None,
        intree: dict[str, float] | None,
        waivable: frozenset[tuple[str, str]],
    ) -> Self:
        self = super().__new__(cls)
        self._path = path
        self._base_present = base is not None
        if base is None:
            self._review_new(current)
        else:
            self._review_tracked(current, base, intree, waivable)
        return self

    def _review_new(self, current: dict[str, float]) -> None:
        rows: list[Row] = []
        regressed: list[str] = []
        for metric in Thresholds.names():
            if metric not in current:
                continue
            val = current[metric]
            passed = Thresholds.meets(metric, val)
            grade = "PASS" if passed else "FAIL"
            rows.append(Row(self._path, metric, "NEW", f"{val:.3f}", "--", grade))
            if not passed:
                regressed.append(metric)
        self._rows = tuple(rows)
        self._regressed = tuple(regressed)
        self._waived = ()
        self._improved = False
        self._new_passes = not regressed

    def _review_tracked(
        self,
        current: dict[str, float],
        base: dict[str, float],
        intree: dict[str, float] | None,
        waivable: frozenset[tuple[str, str]],
    ) -> None:
        rows: list[Row] = []
        regressed: list[str] = []
        waived: list[str] = []
        improved = False
        for metric in Thresholds.names():
            if metric not in current or metric not in base:
                continue
            cur, base_val = current[metric], base[metric]
            status = self._classify(metric, cur, base_val, intree, waivable)
            if status == "IMPROVED":
                improved = True
            elif status == "REGRESSED":
                regressed.append(metric)
            elif status == "RELAXED":
                waived.append(metric)
            delta = cur - base_val
            if delta != 0.0 or status in ("REGRESSED", "RELAXED"):
                rows.append(
                    Row(
                        self._path,
                        metric,
                        f"{base_val:.3f}",
                        f"{cur:.3f}",
                        f"{delta:+.3f}",
                        status,
                    )
                )
        self._rows = tuple(rows)
        self._regressed = tuple(regressed)
        self._waived = tuple(waived)
        self._improved = improved
        self._new_passes = False

    def _classify(
        self,
        metric: str,
        cur: float,
        base_val: float,
        intree: dict[str, float] | None,
        waivable: frozenset[tuple[str, str]],
    ) -> str:
        if Thresholds.strictly_better(metric, cur, base_val):
            return "IMPROVED"
        if Thresholds.better_or_equal(metric, cur, base_val):
            return "PASS"
        locked = intree is not None and intree.get(metric) == cur
        if locked and (self._path, metric) in waivable:
            return "RELAXED"
        return "REGRESSED"

    @property
    def path(self) -> str:
        """Return the reviewed file's repo-relative path."""
        return self._path

    @property
    def rows(self) -> tuple[Row, ...]:
        """Return the metric rows worth reporting for this file."""
        return self._rows

    @property
    def base_present(self) -> bool:
        """Return whether the file existed in the base baseline."""
        return self._base_present

    @property
    def regressed(self) -> tuple[str, ...]:
        """Return the metrics that regressed and were not waived."""
        return self._regressed

    @property
    def waived(self) -> tuple[str, ...]:
        """Return the metrics whose regression was waived by a relaxation."""
        return self._waived

    @property
    def improved(self) -> bool:
        """Return whether an existing metric strictly improved."""
        return self._improved

    @property
    def new_passes(self) -> bool:
        """Return whether a new-vs-base file clears all absolute thresholds."""
        return self._new_passes


class Review:
    """Aggregate per-file reviews into the whole-change ratchet verdict.

    The improvement gate follows S5: when the change touches any file present
    in the base baseline, the required improvement must come from such an
    existing file; a pure-add change is satisfied by new files clearing the
    absolute thresholds and is never forced to also pay down existing debt.
    A change carrying a relaxation waiver is exempt from the gate entirely.
    """

    _reviews: tuple[FileReview, ...]

    def __new__(cls, reviews: tuple[FileReview, ...]) -> Self:
        self = super().__new__(cls)
        self._reviews = reviews
        return self

    @property
    def rows(self) -> tuple[Row, ...]:
        """Return every reportable row across all reviewed files."""
        return tuple(row for review in self._reviews for row in review.rows)

    @property
    def regressions(self) -> tuple[tuple[str, str], ...]:
        """Return the unwaived (path, metric) regressions."""
        return tuple((r.path, metric) for r in self._reviews for metric in r.regressed)

    @property
    def has_regression(self) -> bool:
        """Return whether any unwaived regression exists."""
        return bool(self.regressions)

    @property
    def has_waiver(self) -> bool:
        """Return whether any regression was waived by a relaxation."""
        return any(r.waived for r in self._reviews)

    @property
    def improvement_satisfied(self) -> bool:
        """Return whether the S5 improvement gate is met."""
        if self.has_waiver:
            return True
        existing = [r for r in self._reviews if r.base_present]
        if existing:
            return any(r.improved for r in existing)
        return any(r.new_passes for r in self._reviews)
