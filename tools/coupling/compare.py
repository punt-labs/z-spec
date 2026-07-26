"""Per-file regression review for a coupling ratchet check.

The coupling gate is regression-only: a touched file fails if any metric is
worse than its base baseline. There is no must-improve gate -- holding steady
passes, so a change that only touches unrelated files is never forced to pay
down coupling debt.

A regression is *waived* only when the in-tree baseline has locked the current
value and the audit log records a matching relaxation scoped to this change --
the same audited escape hatch the OO ratchet uses, so a legitimate coupling
increase (e.g. a new public re-export module) can be accepted with a
justification rather than blocked outright.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Self

from .thresholds import CouplingThresholds


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


class CouplingReview:
    """Compare one touched file's current metrics against its baseline entry.

    A file absent from the baseline is a new file: its metrics are reported as
    INFO and never counted as a regression. The base entry already accounts for
    renames -- a rename target inherits its predecessor's baseline, so a
    worsened rename cannot launder its history as a brand-new file.
    """

    _path: str
    _rows: tuple[Row, ...]
    _regressed: tuple[str, ...]
    _waived: tuple[str, ...]

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
        if base is None:
            self._review_new(current)
        else:
            self._review_tracked(current, base, intree, waivable)
        return self

    def _review_new(self, current: dict[str, float]) -> None:
        self._rows = tuple(
            Row(self._path, metric, "NEW", f"{current[metric]:.3f}", "--", "INFO")
            for metric in CouplingThresholds.names()
            if metric in current
        )
        self._regressed = ()
        self._waived = ()

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
        for metric in CouplingThresholds.names():
            if metric not in current or metric not in base:
                continue
            cur, base_val = current[metric], base[metric]
            status = self._classify(metric, cur, base_val, intree, waivable)
            if status == "REGRESSED":
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

    def _classify(
        self,
        metric: str,
        cur: float,
        base_val: float,
        intree: dict[str, float] | None,
        waivable: frozenset[tuple[str, str]],
    ) -> str:
        if CouplingThresholds.strictly_better(metric, cur, base_val):
            return "IMPROVED"
        if CouplingThresholds.better_or_equal(metric, cur, base_val):
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
    def regressed(self) -> tuple[str, ...]:
        """Return the metrics that regressed and were not waived."""
        return self._regressed

    @property
    def waived(self) -> tuple[str, ...]:
        """Return the metrics whose regression was waived by a relaxation."""
        return self._waived
