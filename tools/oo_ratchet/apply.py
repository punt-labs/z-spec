"""Apply an update plan to the baseline: the never-loosening write mechanics."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Self

from .audit import AuditLog
from .baseline import Baseline
from .gitio import GitRepo
from .outcome import Outcome
from .thresholds import Thresholds


@dataclass(frozen=True, slots=True)
class UpdatePlan:
    """Which files an update touches, plus rename, prune, and broken-file intent.

    ``parse_errors`` are paths on disk that failed to AST-parse. They must be
    preserved (never pruned as if deleted) and surfaced as a refusal, so a
    syntax error cannot silently erase a file's baseline history.
    """

    current: dict[str, dict[str, float]]
    touched: frozenset[str]
    renames: dict[str, str] = field(default_factory=dict)
    prune: bool = False
    parse_errors: frozenset[str] = frozenset()


class PlanApplier:
    """Write an ``UpdatePlan`` to the baseline, refusing per-metric regressions.

    A renamed file is compared against its predecessor's carried entry (S8); a
    refusal keeps that entry so the carry survives to the next run; a rename
    source whose target is present is never pruned as a false deletion.
    """

    _baseline: Baseline
    _audit: AuditLog
    _git: GitRepo

    def __new__(cls, baseline: Baseline, audit: AuditLog, git: GitRepo) -> Self:
        self = super().__new__(cls)
        self._baseline = baseline
        self._audit = audit
        self._git = git
        return self

    def apply(self, plan: UpdatePlan, source: str | None) -> Outcome:
        """Apply the plan, save the baseline, append the audit, and report."""
        new_baseline = dict(self._baseline.entries)
        refused: list[tuple[str, str]] = []
        deltas: dict[str, dict[str, list[float]]] = {}
        removed = 0
        for path in sorted(plan.touched):
            if path in plan.parse_errors:
                continue  # on disk but unparseable: keep its row, refuse below
            if path not in plan.current:
                removed += self._drop(new_baseline, path)
                continue
            removed += self._write_or_refuse(new_baseline, plan, path, refused, deltas)
        if plan.prune:
            removed += self._prune_kept(new_baseline, plan)
        broken = sorted(plan.parse_errors)
        self._baseline.save(new_baseline)
        self._audit.append(
            files_scored=len(plan.current),
            files_improved=len(deltas),
            files_regressed=len({p for p, _ in refused}) + len(broken),
            verdict="pass" if not refused and not broken else "fail",
            deltas=deltas,
            source=source,
            commit=self._git.short_head(),
        )
        return self._report(len(deltas), removed, refused, broken)

    def _write_or_refuse(
        self,
        new_baseline: dict[str, dict[str, float]],
        plan: UpdatePlan,
        path: str,
        refused: list[tuple[str, str]],
        deltas: dict[str, dict[str, list[float]]],
    ) -> int:
        entry = plan.current[path]
        base_entry = self._base_for(plan, path)
        regressed = self.regressed(entry, base_entry)
        if regressed:
            # Keep the old rename-source entry so the carried base survives to
            # the next run -- dropping it would let a later run treat the rename
            # as a brand-new file and launder the regression.
            refused.extend((path, m) for m in regressed)
            return 0
        new_baseline[path] = entry
        file_deltas = self.deltas(entry, base_entry)
        if file_deltas:
            deltas[path] = file_deltas
        return self._drop_rename_source(new_baseline, plan, path)

    def _base_for(self, plan: UpdatePlan, path: str) -> dict[str, float] | None:
        base_entry = self._baseline.get(path)
        if base_entry is None and path in plan.renames:
            return self._baseline.get(plan.renames[path])
        return base_entry

    def _drop_rename_source(
        self, new_baseline: dict[str, dict[str, float]], plan: UpdatePlan, path: str
    ) -> int:
        old = plan.renames.get(path)
        if old is not None:
            return self._drop(new_baseline, old)
        return 0

    @staticmethod
    def _drop(new_baseline: dict[str, dict[str, float]], path: str) -> int:
        if path in new_baseline:
            del new_baseline[path]
            return 1
        return 0

    @staticmethod
    def _prune_kept(new_baseline: dict[str, dict[str, float]], plan: UpdatePlan) -> int:
        # Prune only genuine deletions. A file present on disk is either
        # parse-clean (in ``current``) or a parse error; a rename source is kept
        # whenever its target is present on disk at all -- parseable or not --
        # so a rename to an unparseable target never drops the old row.
        present = plan.current.keys() | plan.parse_errors
        rename_sources = frozenset(
            old for new, old in plan.renames.items() if new in present
        )
        kept = present | rename_sources
        stale = [p for p in new_baseline if p not in kept]
        for p in stale:
            del new_baseline[p]
        return len(stale)

    @staticmethod
    def regressed(entry: dict[str, float], base: dict[str, float] | None) -> list[str]:
        """Return the metrics in ``entry`` worse than ``base`` (empty if new)."""
        if base is None:
            return []
        return [
            m
            for m in entry
            if m in base and not Thresholds.better_or_equal(m, entry[m], base[m])
        ]

    @staticmethod
    def deltas(
        entry: dict[str, float], base: dict[str, float] | None
    ) -> dict[str, list[float]]:
        """Return the changed metrics as ``{metric: [old, new]}``."""
        if base is None:
            return {m: [0.0, entry[m]] for m in entry}
        return {
            m: [base[m], entry[m]] for m in entry if m in base and entry[m] != base[m]
        }

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
