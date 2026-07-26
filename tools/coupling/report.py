"""Render a coupling scorer's results as human and JSON reports."""

from __future__ import annotations

import json
from typing import Self

from .scorer import CouplingScorer
from .thresholds import CouplingThresholds


class CouplingReport:
    """Format a scorer's per-file, aggregate, and package metrics for display."""

    _scorer: CouplingScorer

    def __new__(cls, scorer: CouplingScorer) -> Self:
        self = super().__new__(cls)
        self._scorer = scorer
        return self

    def render_table(self) -> list[str]:
        """Return the aggregate metric table as report lines."""
        summary = self._scorer.summary
        grades = self._scorer.grades
        lines = [
            f"\n{'Metric':<28} {'Value':>8} {'Target':>10} {'Grade':>6}",
            "-" * 56,
        ]
        for k in CouplingThresholds.names():
            if k not in summary:
                continue
            op, target = CouplingThresholds.TABLE[k]
            grade = grades[k]
            marker = "  " if grade == "PASS" else " *"
            lines.append(f"{k:<28} {summary[k]:>8.2f} {op} {target:<8} {grade}{marker}")
        return lines

    def render_packages(self) -> list[str]:
        """Return the package-level metric table as report lines."""
        pkgs = self._scorer.packages
        if not pkgs:
            return []
        lines = [
            "\n--- Package-level metrics ---",
            f"\n  {'Package':<20} {'Modules':>8} {'Ext Deps':>9} "
            f"{'Interface':>10} {'Density':>8} {'Cohesion':>9}",
            "  " + "-" * 68,
        ]
        lines.extend(
            f"  {p.package:<20} {p.modules:>8} {p.pkg_efferent_coupling:>9} "
            f"{p.pkg_interface_width:>10} {p.pkg_intra_density:>8.3f} "
            f"{p.pkg_cohesion:>9.3f}"
            for p in pkgs
        )
        return lines

    def render_per_file(self) -> list[str]:
        """Return the per-file breakdown, honoring the ``__main__`` relaxation."""
        lines = ["\n--- Per-file breakdown ---"]
        for r in self._scorer.results:
            fpath = str(r.get("file", "?"))
            lines.append(f"\n  {fpath}")
            for k, v in r.items():
                if k == "file" or k not in CouplingThresholds.TABLE:
                    continue
                passed = CouplingThresholds.meets(k, float(v), fpath)
                grade = "PASS" if passed else "FAIL"
                lines.append(f"    {k:<26} {v:>8} {grade}")
        return lines

    def to_json(self) -> str:
        """Return per-file, aggregate, grades, and thresholds as JSON."""
        output = {
            "per_file": self._scorer.results,
            "packages": [p.as_dict() for p in self._scorer.packages],
            "aggregate": self._scorer.summary,
            "grades": self._scorer.grades,
            "thresholds": {
                k: CouplingThresholds.describe(k) for k in CouplingThresholds.names()
            },
        }
        return json.dumps(output, indent=2)
