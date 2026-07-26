"""The in-tree baseline file: load, query, save, and project scorer results."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Self

from .thresholds import Thresholds


class BaselineError(Exception):
    """The in-tree ``.oo-baseline.json`` could not be parsed.

    Raised instead of letting ``json.JSONDecodeError`` escape, so a corrupt or
    hand-broken baseline becomes a controlled non-zero outcome (``Cli.run``
    catches it) rather than a traceback out of the gate.
    """


class Baseline:
    """Read and write ``.oo-baseline.json`` — the committed metric snapshot."""

    _path: Path
    _entries: dict[str, dict[str, float]]

    FILENAME: str = ".oo-baseline.json"

    def __new__(cls, root: Path) -> Self:
        self = super().__new__(cls)
        self._path = root / cls.FILENAME
        self._entries = cls._load(self._path)
        return self

    @property
    def path(self) -> Path:
        """Return the on-disk baseline path."""
        return self._path

    @property
    def exists(self) -> bool:
        """Return whether the baseline file is present on disk."""
        return self._path.exists()

    @property
    def entries(self) -> dict[str, dict[str, float]]:
        """Return the full baseline mapping of path to metric values."""
        return self._entries

    def get(self, path: str) -> dict[str, float] | None:
        """Return the baseline metrics for a path, or ``None`` if untracked."""
        return self._entries.get(path)

    @staticmethod
    def _load(path: Path) -> dict[str, dict[str, float]]:
        if not path.exists():
            return {}
        try:
            loaded = json.loads(path.read_text())
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            msg = f"unreadable baseline file {path}: {exc}"
            raise BaselineError(msg) from exc
        if not isinstance(loaded, dict):
            msg = f"non-dict baseline file {path}"
            raise BaselineError(msg)
        # Each value must be a per-metric dict; a non-dict value would make
        # ``metric not in entry`` a substring test that skips every metric.
        if not all(isinstance(v, dict) for v in loaded.values()):
            msg = f"non-dict entry in baseline file {path}"
            raise BaselineError(msg)
        # Each metric value must be a real number: a bool would compare as 0/1
        # (fail-open) and a string would raise TypeError in the comparison.
        if not all(
            isinstance(m, (int, float)) and not isinstance(m, bool)
            for entry in loaded.values()
            for m in entry.values()
        ):
            msg = f"non-numeric metric in baseline file {path}"
            raise BaselineError(msg)
        parsed: dict[str, dict[str, float]] = loaded
        return parsed

    def save(self, data: dict[str, dict[str, float]]) -> None:
        """Write ``data`` sorted by path and refresh the in-memory view."""
        ordered = dict(sorted(data.items()))
        self._path.write_text(json.dumps(ordered, indent=2) + "\n")
        self._entries = ordered

    @staticmethod
    def metrics_by_file(
        results: list[dict[str, float | int | str]],
    ) -> dict[str, dict[str, float]]:
        """Project scorer results into the baseline shape, skipping errors."""
        out: dict[str, dict[str, float]] = {}
        for r in results:
            if "error" in r:
                continue
            metrics = {k: float(r[k]) for k in Thresholds.names() if k in r}
            out[str(r["file"])] = metrics
        return out
