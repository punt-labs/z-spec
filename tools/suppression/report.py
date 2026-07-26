"""Aggregate per-file suppression counts into a whole-tree report."""

from __future__ import annotations

import json
from typing import Self

from .patterns import CATEGORIES, PATTERN_NAMES, FileSuppressions


class SuppressionReport:
    """Aggregate suppression counts across files and render them."""

    _total: int
    _by_category: dict[str, int]
    _by_file: dict[str, dict[str, int]]

    def __new__(
        cls,
        file_results: list[FileSuppressions],
        per_file_ignores_count: int,
    ) -> Self:
        self = super().__new__(cls)
        self._by_category = dict.fromkeys(CATEGORIES, 0)
        self._by_category["per_file_ignores"] = per_file_ignores_count
        self._by_file = {}
        for fs in file_results:
            for name in PATTERN_NAMES:
                self._by_category[name] += fs.count(name)
            if fs.total > 0:
                self._by_file[fs.path] = fs.to_dict()
        self._total = sum(self._by_category.values())
        return self

    @property
    def total(self) -> int:
        """Return the total suppression count across all files and config."""
        return self._total

    @property
    def by_category(self) -> dict[str, int]:
        """Return the suppression count per category."""
        return dict(self._by_category)

    @property
    def by_file(self) -> dict[str, dict[str, int]]:
        """Return the non-zero suppression counts per file."""
        return dict(self._by_file)

    def to_json(self) -> str:
        """Return the report as machine-readable JSON."""
        return json.dumps(
            {
                "total": self._total,
                "by_category": self._by_category,
                "by_file": self._by_file,
            },
            indent=2,
        )

    def render(self) -> list[str]:
        """Return the human-readable summary as report lines."""
        lines = [
            f"\nTotal suppressions: {self._total}",
            f"\n{'Category':<20} {'Count':>6}",
            "-" * 28,
        ]
        lines.extend(
            f"{category:<20} {count:>6}"
            for category, count in sorted(self._by_category.items())
        )
        return lines

    def render_threshold(self) -> list[str]:
        """Return the per-file breakdown as report lines."""
        lines = ["\n--- Per-file breakdown ---"]
        if not self._by_file:
            lines.append("  (no suppressions found)")
            return lines
        for fpath in sorted(self._by_file):
            counts = self._by_file[fpath]
            lines.append(f"\n  {fpath}  (total: {sum(counts.values())})")
            lines.extend(
                f"    {cat:<20} {count:>4}" for cat, count in sorted(counts.items())
            )
        return lines
