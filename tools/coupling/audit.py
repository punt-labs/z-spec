"""The append-only audit log of coupling baseline verdicts."""

from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Self


class CouplingAuditError(Exception):
    """The ``.oo-coupling-audit.jsonl`` log could not be read or parsed.

    Raised instead of letting an OSError, UnicodeDecodeError, or JSONDecodeError
    escape ``render_log`` (the ``--log`` view), so a corrupt or unreadable audit
    log becomes a controlled non-zero the CLI catches, not a traceback.
    """


class CouplingAudit:
    """Append and render ``.oo-coupling-audit.jsonl`` — the ratchet's trail."""

    _path: Path

    FILENAME: str = ".oo-coupling-audit.jsonl"

    def __new__(cls, root: Path) -> Self:
        self = super().__new__(cls)
        self._path = root / cls.FILENAME
        return self

    @property
    def path(self) -> Path:
        """Return the on-disk audit log path."""
        return self._path

    @property
    def exists(self) -> bool:
        """Return whether the audit log is present on disk."""
        return self._path.exists()

    def append(
        self,
        *,
        files_scored: int,
        files_improved: int,
        files_regressed: int,
        verdict: str,
        deltas: dict[str, dict[str, list[float]]],
        commit: str | None,
        source: str | None = None,
        reason: str | None = None,
    ) -> None:
        """Append one verdict entry, recording its source (PR/bead ref).

        ``reason`` carries the human justification for a ``relaxed`` verdict;
        it is an audit marker, not an enforcement gate.
        """
        entry = {
            "ts": datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "commit": commit,
            "source": source,
            "files_scored": files_scored,
            "files_improved": files_improved,
            "files_regressed": files_regressed,
            "verdict": verdict,
            "reason": reason,
            "deltas": deltas,
        }
        with self._path.open("a") as f:
            f.write(json.dumps(entry, separators=(",", ":")) + "\n")

    def relaxations_since(self, base_text: str | None) -> frozenset[tuple[str, str]]:
        """Return (file, metric) pairs relaxed by the *current* change only.

        A relaxation counts only when its audit entry is absent from the base
        commit's audit log (``base_text``). This scopes the waiver to the
        change under review, so a historical relaxation cannot bless a fresh
        regression re-locked via ``--rebaseline``.

        Entries are matched *structurally* -- by canonical JSON -- so a reformat
        of the base log (whitespace, key order) does not make a base relaxation
        look new and over-waive it.
        """
        base_keys = self._canonical_set(base_text)
        pairs: set[tuple[str, str]] = set()
        for line in self._raw_lines():
            entry = self._parse(line)
            if self._canonical(entry) in base_keys:
                continue
            if entry.get("verdict") != "relaxed":
                continue
            deltas = entry.get("deltas")
            if not isinstance(deltas, dict):
                continue
            for path, metrics in deltas.items():
                if isinstance(metrics, dict):
                    pairs.update((path, metric) for metric in metrics)
        return frozenset(pairs)

    @classmethod
    def _canonical_set(cls, base_text: str | None) -> frozenset[str]:
        if not base_text:
            return frozenset()
        return frozenset(
            cls._canonical(cls._parse(line))
            for line in base_text.splitlines()
            if line.strip()
        )

    @staticmethod
    def _canonical(entry: dict[str, object]) -> str:
        """Return a formatting-independent identity for an audit entry."""
        return json.dumps(entry, sort_keys=True)

    @staticmethod
    def _parse(line: str) -> dict[str, object]:
        """Parse one audit line, or raise ``CouplingAuditError`` naming it."""
        try:
            parsed: dict[str, object] = json.loads(line)
        except json.JSONDecodeError as exc:
            msg = f"malformed coupling audit entry {line[:80]!r}: {exc}"
            raise CouplingAuditError(msg) from exc
        return parsed

    def _raw_lines(self) -> list[str]:
        if not self._path.exists():
            return []
        return [ln for ln in self._path.read_text().splitlines() if ln.strip()]

    def render_log(self) -> list[str]:
        """Return the audit history as report lines."""
        if not self._path.exists():
            return ["No audit log found"]
        try:
            text = self._path.read_text()
        except (OSError, UnicodeDecodeError) as exc:
            msg = f"unreadable coupling audit log {self._path}: {exc}"
            raise CouplingAuditError(msg) from exc
        lines = [
            f"\n{'Timestamp':<22} {'Commit':<10} {'Scored':>7} "
            f"{'Improved':>9} {'Regressed':>10} {'Verdict':>12}",
            "-" * 74,
        ]
        for raw in text.splitlines():
            if not raw.strip():
                continue
            try:
                entry = json.loads(raw)
            except json.JSONDecodeError as exc:
                msg = f"corrupt coupling audit log {self._path}: {exc}"
                raise CouplingAuditError(msg) from exc
            commit = entry.get("commit") or "?"
            lines.append(
                f"{entry.get('ts', '?')!s:<22} {commit!s:<10} "
                f"{entry.get('files_scored', 0)!s:>7} "
                f"{entry.get('files_improved', 0)!s:>9} "
                f"{entry.get('files_regressed', 0)!s:>10} "
                f"{entry.get('verdict', '?')!s:>12}"
            )
        return lines
