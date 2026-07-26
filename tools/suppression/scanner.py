"""Scan a file or directory tree for suppression comments."""

from __future__ import annotations

from pathlib import Path
from typing import Self

from .patterns import FileSuppressions
from .pyproject import PerFileIgnoresCounter
from .report import SuppressionReport


class Scanner:
    """Discover Python files under a target and build a suppression report."""

    _report: SuppressionReport

    def __new__(cls, target: Path, project_root: Path | None = None) -> Self:
        self = super().__new__(cls)
        root = project_root if project_root is not None else Path.cwd()
        file_results = self._collect_files(target)
        pfi = PerFileIgnoresCounter(root / "pyproject.toml")
        self._report = SuppressionReport(file_results, pfi.total)
        return self

    @property
    def report(self) -> SuppressionReport:
        """Return the aggregated suppression report."""
        return self._report

    @staticmethod
    def _collect_files(target: Path) -> list[FileSuppressions]:
        if target.is_file():
            return [FileSuppressions(str(target), target.read_text())]
        if not target.is_dir():
            return []
        results: list[FileSuppressions] = []
        for py_file in sorted(target.rglob("*.py")):
            if py_file.name.startswith("."):
                continue
            # Let an unreadable file raise OSError. As a CI gate, swallowing it
            # would undercount a file that has NEW suppressions -- the total
            # wouldn't rise and a real regression would pass. Fail closed instead;
            # the CLI turns the OSError into a controlled non-zero.
            results.append(FileSuppressions(str(py_file), py_file.read_text()))
        return results
