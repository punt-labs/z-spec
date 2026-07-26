"""Score a file or directory of modules for coupling and cohesion."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Self

from .graph import ImportGraph
from .imports import ImportResolver
from .layout import PackageLayout
from .metrics import ModuleCouplingMetrics
from .packages import PackageMetrics, PackageScorer
from .thresholds import CouplingThresholds


class CouplingScorer:
    """Score modules against coupling/cohesion thresholds.

    Keys are normalized repo-relative (POSIX) against ``repo_root`` so scorer
    output, baseline keys, and git-diff paths all intersect cleanly regardless
    of how the target path was spelled on the command line.
    """

    _results: list[dict[str, float | int | str]]
    _packages: tuple[PackageMetrics, ...]

    def __new__(cls, target: Path, repo_root: Path | None = None) -> Self:
        self = super().__new__(cls)
        root = repo_root if repo_root is not None else Path.cwd()
        if target.is_file():
            layout = PackageLayout(target.parent)
            self._results = [self._safe_score(target, layout, frozenset(), root)]
            self._packages = ()
        elif target.is_dir():
            layout = PackageLayout(target)
            graph = ImportGraph.build(layout)
            self._results = self._score_directory(layout, graph, root)
            self._packages = tuple(PackageScorer(layout, graph).score())
        else:
            self._results = []
            self._packages = ()
        return self

    @property
    def results(self) -> list[dict[str, float | int | str]]:
        """Return the per-file metric dicts."""
        return self._results

    @property
    def packages(self) -> tuple[PackageMetrics, ...]:
        """Return the per-sub-package metrics."""
        return self._packages

    @property
    def files(self) -> frozenset[str]:
        """Return the repo-relative paths the scorer enumerated (parse-clean)."""
        return frozenset(str(r["file"]) for r in self._results if "error" not in r)

    @property
    def parse_errors(self) -> frozenset[str]:
        """Return the paths that failed to AST-parse (excluded from scoring)."""
        return frozenset(str(r["file"]) for r in self._results if "error" in r)

    @property
    def summary(self) -> dict[str, float]:
        """Return the aggregated metric summary across all scored files."""
        return self._aggregate()

    @property
    def grades(self) -> dict[str, str]:
        """Return PASS/FAIL per aggregated metric against the strict table."""
        return {
            k: "PASS" if CouplingThresholds.meets(k, v) else "FAIL"
            for k, v in self.summary.items()
        }

    @property
    def fail_count(self) -> int:
        """Return the number of aggregated metrics failing their threshold."""
        return sum(1 for g in self.grades.values() if g == "FAIL")

    def _score_directory(
        self, layout: PackageLayout, graph: ImportGraph, root: Path
    ) -> list[dict[str, float | int | str]]:
        cycle = frozenset(graph.cycle_members())
        return [self._safe_score(f, layout, cycle, root) for f in layout.root_files()]

    def _safe_score(
        self,
        py_file: Path,
        layout: PackageLayout,
        cycle: frozenset[str],
        root: Path,
    ) -> dict[str, float | int | str]:
        key = self._normalize(py_file, root)
        try:
            tree = ast.parse(py_file.read_text(), filename=str(py_file))
        except (SyntaxError, OSError, UnicodeDecodeError) as exc:
            # A file that cannot be read or decoded is scored as an error, like a
            # syntax error: the ratchet fails on it if it is a touched file
            # (fail-closed), rather than crashing the whole scoring pass.
            return {"file": key, "error": str(exc)}
        mod_key = layout.key_for(py_file)
        resolver = ImportResolver(mod_key, layout.modules, layout.name)
        metrics = ModuleCouplingMetrics(key, tree, resolver).compute()
        metrics["circular_imports"] = 1 if mod_key in cycle else 0
        return metrics

    @staticmethod
    def _normalize(path: Path, root: Path) -> str:
        resolved = path.resolve()
        try:
            return resolved.relative_to(root.resolve()).as_posix()
        except ValueError:
            return path.as_posix()

    def _aggregate(self) -> dict[str, float]:
        agg: dict[str, list[float]] = {k: [] for k in CouplingThresholds.names()}
        for r in self._results:
            if "error" in r:
                continue
            for k in CouplingThresholds.names():
                if k in r:
                    agg[k].append(float(r[k]))
        summary: dict[str, float] = {}
        for k, values in agg.items():
            if not values:
                continue
            if k in CouplingThresholds.MAX_AGGREGATED:
                summary[k] = max(values)
            else:
                summary[k] = round(sum(values) / len(values), 3)
        return summary
