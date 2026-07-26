"""Coupling baseline mutations: scoped never-loosen update and rebaseline.

``update`` is scoped to the whole PR (``merge-base..worktree``) and refuses any
per-metric regression, so it tightens the baseline but never loosens it.
``rebaseline`` is the explicit whole-tree reset. Both refuse to run under
``GITHUB_ACTIONS`` unless ``--allow-ci-write`` is passed.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Self

from .audit import CouplingAudit
from .baseline import CouplingBaseline
from .gitio import GitRepo
from .outcome import Outcome
from .thresholds import CouplingThresholds

if TYPE_CHECKING:
    from .scorer import CouplingScorer


class CouplingWriter:
    """Apply never-loosening coupling baseline updates and whole-tree resets."""

    _baseline: CouplingBaseline
    _audit: CouplingAudit
    _git: GitRepo

    def __new__(cls, root: Path, git: GitRepo) -> Self:
        self = super().__new__(cls)
        self._baseline = CouplingBaseline(root)
        self._audit = CouplingAudit(root)
        self._git = git
        return self

    def update(
        self,
        scorer: CouplingScorer,
        *,
        base_ref: str | None,
        require_base: bool,
        allow_ci_write: bool,
        source: str | None,
    ) -> Outcome:
        """Update baseline entries for PR-touched files, never loosening.

        Mirrors ``check``'s fail-closed contract: on an unresolvable base a
        scoped update refuses rather than silently sweeping the whole tree. A
        genuine first-adoption (no in-tree baseline) bootstraps the whole tree.
        """
        blocked = self._guard(allow_ci_write=allow_ci_write)
        if blocked is not None:
            return blocked
        current = CouplingBaseline.metrics_by_file(scorer.results)
        base = self._git.resolve_base(base_ref)
        if base is None:
            scope = self._no_base_scope(require_base=require_base)
            if scope is not None:
                return scope
            return self._apply(
                current, frozenset(current), {}, scorer.parse_errors, source
            )
        diff = self._git.diff(base)
        touched = diff.python_files()
        return self._apply(
            current, touched, diff.renames, touched & scorer.parse_errors, source
        )

    def rebaseline(
        self, scorer: CouplingScorer, *, allow_ci_write: bool, source: str | None
    ) -> Outcome:
        """Reset the coupling baseline unconditionally to current scores."""
        blocked = self._guard(allow_ci_write=allow_ci_write)
        if blocked is not None:
            return blocked
        current = CouplingBaseline.metrics_by_file(scorer.results)
        self._baseline.save(current)
        self._audit.append(
            files_scored=len(current),
            files_improved=0,
            files_regressed=0,
            verdict="rebaseline",
            deltas={},
            commit=self._git.short_head(),
            source=source,
        )
        return Outcome.passed(
            f"\nBaseline reset: {self._baseline.path}",
            f"  files scored: {len(current)}",
        )

    def relax(
        self,
        scorer: CouplingScorer,
        file: str,
        *,
        justify: str,
        allow_ci_write: bool,
        source: str | None,
    ) -> Outcome:
        """Write ``file``'s current metrics even if looser, with justification.

        The single sanctioned, audited loosening -- the escape hatch a legitimate
        coupling increase needs. Records ONLY the metrics that actually worsened
        against the pre-relax baseline, so relaxing one metric never blesses a
        future regression of another metric on the same file.
        """
        blocked = self._guard(allow_ci_write=allow_ci_write)
        if blocked is not None:
            return blocked
        if not justify.strip():
            return Outcome.failed("FAIL: --relax requires a non-empty --justify")
        current = CouplingBaseline.metrics_by_file(scorer.results)
        entry = current.get(file)
        if entry is None:
            return Outcome.failed(f"FAIL: not a scored file: {file}")
        base_entry = self._baseline.get(file)
        if base_entry is None:
            return Outcome.failed(
                f"FAIL: {file} has no baseline entry to relax; "
                "use --update or --rebaseline to add a new file"
            )
        loosened = self._regressed(entry, base_entry)
        if not loosened:
            return Outcome.failed(
                f"FAIL: nothing to relax for {file} "
                "(no metric is worse than its baseline)"
            )
        deltas = {file: {m: [base_entry.get(m, entry[m]), entry[m]] for m in loosened}}
        new_baseline = dict(self._baseline.entries)
        new_baseline[file] = entry
        self._baseline.save(new_baseline)
        self._audit.append(
            files_scored=len(current),
            files_improved=0,
            files_regressed=1,
            verdict="relaxed",
            deltas=deltas,
            commit=self._git.short_head(),
            source=source,
            reason=justify,
        )
        return Outcome.passed(
            f"\nRelaxed {file} (reason: {justify})",
            f"  baseline: {self._baseline.path}",
        )

    def _apply(
        self,
        current: dict[str, dict[str, float]],
        touched: frozenset[str],
        renames: dict[str, str],
        parse_errors: frozenset[str],
        source: str | None,
    ) -> Outcome:
        new_baseline = dict(self._baseline.entries)
        refused: list[tuple[str, str]] = []
        deltas: dict[str, dict[str, list[float]]] = {}
        removed = 0
        for path in sorted(touched):
            if path in parse_errors:
                continue  # on disk but unparseable: keep its row, refuse below
            if path not in current:
                removed += self._drop(new_baseline, path)
                continue
            removed += self._write_or_refuse(
                new_baseline, current, path, renames, refused, deltas
            )
        broken = sorted(parse_errors)
        self._baseline.save(new_baseline)
        self._audit.append(
            files_scored=len(current),
            files_improved=len(deltas),
            files_regressed=len({p for p, _ in refused}) + len(broken),
            verdict="pass" if not refused and not broken else "fail",
            deltas=deltas,
            commit=self._git.short_head(),
            source=source,
        )
        return self._report(len(deltas), removed, refused, broken)

    def _write_or_refuse(
        self,
        new_baseline: dict[str, dict[str, float]],
        current: dict[str, dict[str, float]],
        path: str,
        renames: dict[str, str],
        refused: list[tuple[str, str]],
        deltas: dict[str, dict[str, list[float]]],
    ) -> int:
        entry = current[path]
        base_entry = self._base_for(path, renames)
        regressed = self._regressed(entry, base_entry)
        if regressed:
            # Keep the old rename-source entry so the carried base survives to a
            # later run -- dropping it would launder the regression as a new file.
            refused.extend((path, m) for m in regressed)
            return 0
        new_baseline[path] = entry
        file_deltas = self._deltas(entry, base_entry)
        if file_deltas:
            deltas[path] = file_deltas
        old = renames.get(path)
        return self._drop(new_baseline, old) if old is not None else 0

    def _base_for(self, path: str, renames: dict[str, str]) -> dict[str, float] | None:
        base_entry = self._baseline.get(path)
        if base_entry is None and path in renames:
            return self._baseline.get(renames[path])
        return base_entry

    @staticmethod
    def _regressed(entry: dict[str, float], base: dict[str, float] | None) -> list[str]:
        if base is None:
            return []
        return [
            m
            for m in entry
            if m in base
            and not CouplingThresholds.better_or_equal(m, entry[m], base[m])
        ]

    @staticmethod
    def _deltas(
        entry: dict[str, float], base: dict[str, float] | None
    ) -> dict[str, list[float]]:
        if base is None:
            return {m: [0.0, entry[m]] for m in entry}
        return {
            m: [base[m], entry[m]] for m in entry if m in base and entry[m] != base[m]
        }

    @staticmethod
    def _drop(new_baseline: dict[str, dict[str, float]], path: str) -> int:
        if path in new_baseline:
            del new_baseline[path]
            return 1
        return 0

    def _no_base_scope(self, *, require_base: bool) -> Outcome | None:
        """Fail closed when scoped update cannot resolve a base.

        Returns a failure ``Outcome`` to abort, or ``None`` to permit the
        first-adoption bootstrap (no in-tree baseline yet to protect).
        """
        if require_base:
            return Outcome.failed(
                "FAIL: base ref unresolvable and --require-base is set"
            )
        if self._baseline.exists:
            return Outcome.failed(
                "FAIL: cannot resolve base (origin/main unfetched or stale) with "
                "a coupling baseline present; fetch origin/main, pass --base-ref, "
                "or use --rebaseline for an intentional whole-tree reset"
            )
        return None

    @staticmethod
    def _guard(*, allow_ci_write: bool) -> Outcome | None:
        if os.environ.get("GITHUB_ACTIONS") == "true" and not allow_ci_write:
            return Outcome.failed(
                "FAIL: refusing to write coupling baseline under GITHUB_ACTIONS "
                "without --allow-ci-write"
            )
        return None

    def _report(
        self,
        improved: int,
        removed: int,
        refused: list[tuple[str, str]],
        broken: list[str],
    ) -> Outcome:
        lines = [
            f"\nBaseline updated: {self._baseline.path}",
            f"  files improved: {improved}",
            f"  files removed:  {removed}",
        ]
        if broken:
            lines.append(f"  REFUSED ({len(broken)} unparseable, baseline kept):")
            lines.extend(f"    {p}: parse error" for p in broken)
        if refused:
            lines.append(f"  REFUSED ({len({p for p, _ in refused})} files):")
            lines.extend(f"    {p}: {m} regressed" for p, m in refused)
        if refused or broken:
            return Outcome(1, tuple(lines))
        return Outcome(0, tuple(lines))
