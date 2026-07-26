"""Baseline mutations: scoped update, whole-tree reconcile, relax, rebaseline.

Every mutation refuses per-metric regressions except ``relax`` (the single
sanctioned, audited loosening) and ``rebaseline`` (an explicit structural
reset). All refuse to run under ``GITHUB_ACTIONS`` unless ``--allow-ci-write``.
The write mechanics live in :class:`PlanApplier`; this layer resolves scope,
enforces the fail-closed contract, and dispatches.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Self

from .apply import PlanApplier, UpdatePlan
from .audit import AuditLog
from .baseline import Baseline
from .gitio import GitRepo
from .outcome import Outcome
from .scorer import Scorer


class BaselineWriter:
    """Apply never-loosening baseline updates and audited relaxations."""

    _baseline: Baseline
    _audit: AuditLog
    _git: GitRepo
    _applier: PlanApplier

    def __new__(cls, root: Path, git: GitRepo) -> Self:
        self = super().__new__(cls)
        self._baseline = Baseline(root)
        self._audit = AuditLog(root)
        self._git = git
        self._applier = PlanApplier(self._baseline, self._audit, git)
        return self

    def update(
        self,
        scorer: Scorer,
        *,
        base_ref: str | None,
        require_base: bool,
        allow_ci_write: bool,
        source: str | None,
    ) -> Outcome:
        """Update baseline entries for files in ``base..HEAD`` (never loosens).

        Mirrors ``check``'s fail-closed contract: on an unresolvable base,
        scoped update refuses rather than silently sweeping the whole tree.
        A genuine first-adoption (no in-tree baseline) does bootstrap the whole
        tree; ``--reconcile`` is the explicit opt-in for a whole-tree sweep.

        The base is used only to scope the touched set; the regression check is
        against the *in-tree* baseline (update's job is to tighten it, refusing
        any loosening). No improvement-vs-base is measured here, so a stale or
        diverged branch cannot launder a regression through update -- the
        merge-base comparison lives in ``check``, which reads the base baseline.
        """
        blocked = self._guard(allow_ci_write=allow_ci_write)
        if blocked is not None:
            return blocked
        current = Baseline.metrics_by_file(scorer.results)
        base = self._git.resolve_base(base_ref)
        if base is None:
            bootstrap = self._no_base_scope(require_base=require_base)
            if bootstrap is not None:
                return bootstrap
            plan = UpdatePlan(
                current, frozenset(current), parse_errors=scorer.parse_errors
            )
        else:
            diff = self._git.diff(base)
            touched = diff.python_files()
            plan = UpdatePlan(
                current,
                touched,
                diff.renames,
                parse_errors=touched & scorer.parse_errors,
            )
        return self._applier.apply(plan, source)

    def reconcile(
        self, scorer: Scorer, *, allow_ci_write: bool, source: str | None
    ) -> Outcome:
        """Sweep the whole tree, adding improvements and pruning deletions.

        Rename-aware: the merge-base diff supplies the rename map so a renamed
        module is compared against its predecessor's baseline (refusing a
        regressed rename) and the old key is not pruned as a false deletion.
        """
        blocked = self._guard(allow_ci_write=allow_ci_write)
        if blocked is not None:
            return blocked
        current = Baseline.metrics_by_file(scorer.results)
        base = self._git.resolve_base(None)
        if base is None:
            # Without a base there is no rename provenance; running would prune a
            # rename source and write a regressed rename as new. Fail closed when
            # a baseline exists; only genuine first-adoption bootstraps the tree.
            if self._baseline.exists:
                return Outcome.failed(
                    "FAIL: cannot resolve base for reconcile (origin/main "
                    "unfetched or stale) with an in-tree baseline present; "
                    "fetch origin/main"
                )
            renames: dict[str, str] = {}
        else:
            renames = self._git.diff(base).renames
        plan = UpdatePlan(
            current,
            frozenset(current),
            renames,
            prune=True,
            parse_errors=scorer.parse_errors,
        )
        return self._applier.apply(plan, source)

    def relax(
        self,
        scorer: Scorer,
        file: str,
        *,
        justify: str,
        allow_ci_write: bool,
        source: str | None,
    ) -> Outcome:
        """Write ``file``'s current metrics even if looser, with justification."""
        blocked = self._guard(allow_ci_write=allow_ci_write)
        if blocked is not None:
            return blocked
        if not justify.strip():
            return Outcome.failed("FAIL: --relax requires a non-empty --justify")
        current = Baseline.metrics_by_file(scorer.results)
        entry = current.get(file)
        if entry is None:
            return Outcome.failed(f"FAIL: not a scored file: {file}")
        base_entry = self._baseline.get(file)
        if base_entry is None:
            # A file with no prior baseline has nothing to loosen; relaxing it
            # would forge a "relaxed" entry for a brand-new file. Add it via
            # --update / --reconcile instead.
            return Outcome.failed(
                f"FAIL: {file} has no baseline entry to relax; "
                "use --update or --reconcile to add a new file"
            )
        # Record ONLY the metrics this relaxation actually loosened (worse than
        # the pre-relax baseline). A metric that held or improved is not waivable
        # -- otherwise relaxing M1 would silently bless a future regression of an
        # untouched M2 on the same file.
        loosened = PlanApplier.regressed(entry, base_entry)
        if not loosened:
            # Nothing is worse than the baseline: a relax here would write a
            # no-op "relaxed" line. Refuse instead of recording an empty waiver.
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
            source=source,
            commit=self._git.short_head(),
            reason=justify,
        )
        return Outcome.passed(
            f"\nRelaxed {file} (reason: {justify})",
            f"  baseline: {self._baseline.path}",
        )

    def rebaseline(
        self, scorer: Scorer, *, allow_ci_write: bool, source: str | None
    ) -> Outcome:
        """Reset the baseline unconditionally to current scores."""
        blocked = self._guard(allow_ci_write=allow_ci_write)
        if blocked is not None:
            return blocked
        current = Baseline.metrics_by_file(scorer.results)
        self._baseline.save(current)
        self._audit.append(
            files_scored=len(current),
            files_improved=0,
            files_regressed=0,
            verdict="rebaseline",
            deltas={},
            source=source,
            commit=self._git.short_head(),
        )
        return Outcome.passed(
            f"\nBaseline reset: {self._baseline.path}",
            f"  files scored: {len(current)}",
        )

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
                "an in-tree baseline present; fetch origin/main, pass --base-ref, "
                "or use --reconcile for an intentional whole-tree sweep"
            )
        return None

    @staticmethod
    def _guard(*, allow_ci_write: bool) -> Outcome | None:
        if os.environ.get("GITHUB_ACTIONS") == "true" and not allow_ci_write:
            return Outcome.failed(
                "FAIL: refusing to write baseline under GITHUB_ACTIONS "
                "without --allow-ci-write"
            )
        return None
