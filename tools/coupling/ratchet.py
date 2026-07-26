"""Coupling ratchet check: touched files must not regress against the baseline.

The touched set is scoped to the whole PR (``merge-base..worktree``), not the
last commit, so a coupling regression introduced in an earlier commit and not
re-touched in the final commit is still scored. The comparison baseline is the
one committed at the base commit (regression-only), so a PR cannot launder a
regression by editing the in-tree baseline; the in-tree file is used only on the
local, no-base path.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Self

from .audit import CouplingAudit
from .baseline import CouplingBaseline
from .compare import CouplingReview, Row
from .gitio import GitRepo
from .outcome import Outcome

if TYPE_CHECKING:
    from .scorer import CouplingScorer

_HEADER = (
    f"\n{'File':<40} {'Metric':<26} {'Baseline':>10} "
    f"{'Current':>10} {'Delta':>8} {'Status':>10}"
)


class CouplingRatchet:
    """Enforce the coupling gate: touched files must not regress vs baseline."""

    _baseline: CouplingBaseline
    _audit: CouplingAudit
    _git: GitRepo

    def __new__(cls, root: Path, git: GitRepo) -> Self:
        self = super().__new__(cls)
        self._baseline = CouplingBaseline(root)
        self._audit = CouplingAudit(root)
        self._git = git
        return self

    def check(
        self, scorer: CouplingScorer, *, base_ref: str | None, require_base: bool
    ) -> Outcome:
        """Compare PR-touched files against the base-commit coupling baseline.

        The comparison baseline is read from the base commit
        (``git show <base>:.oo-coupling-baseline.json``), not the worktree file,
        so a PR cannot launder a regression by hand-editing the in-tree baseline
        in the same change. The in-tree file is used only for the local,
        no-base-resolvable path (never under ``--require-base``).
        """
        base = self._git.resolve_base(base_ref)
        if base is None:
            return self._no_base(require_base=require_base)
        base_baseline = self._git.show_baseline(base)
        if base_baseline is None:
            return self._absent_base_baseline()
        if not base_baseline and require_base:
            return self._empty_baseline()
        # An empty {} baseline without --require-base flows to _check_against:
        # every touched file is new/INFO (no regression), but the touched-file
        # parse check still runs, matching the OO ratchet.
        return self._check_against(scorer, base, base_baseline)

    def show_log(self) -> Outcome:
        """Return the audit history as an outcome."""
        return Outcome.passed(*self._audit.render_log())

    def _check_against(
        self,
        scorer: CouplingScorer,
        base: str,
        base_baseline: dict[str, dict[str, float]],
    ) -> Outcome:
        diff = self._git.diff(base)
        touched_py = diff.python_files()
        broken = sorted(touched_py & scorer.parse_errors)
        if broken:
            lines = ["FAIL: touched file(s) failed to parse:"]
            lines.extend(f"  {path}" for path in broken)
            return Outcome(1, tuple(lines))
        current = CouplingBaseline.metrics_by_file(scorer.results)
        touched = sorted(touched_py & scorer.files)
        if not touched:
            return Outcome.passed(
                "No scored Python files touched (gate covers src/punt_vox/)"
            )
        waivable = self._audit.relaxations_since(self._git.show_audit(base))
        reviews = self._build_reviews(
            touched, current, base_baseline, diff.renames, waivable
        )
        return self._verdict(reviews)

    def _no_base(self, *, require_base: bool) -> Outcome:
        """Decide the verdict when no comparison base can be resolved.

        Matches the OO ratchet's ``_no_base`` contract exactly: fail closed under
        ``--require-base``; a genuine first-adoption (no in-tree baseline at all)
        passes so the first baseline can be created; but an in-tree baseline
        present with an unresolvable base means a stale or unfetched
        ``origin/main`` -- fail loud rather than trust a hand-editable file.
        """
        if require_base:
            return Outcome.failed(
                "FAIL: base ref unresolvable and --require-base is set"
            )
        if not self._baseline.exists:
            return Outcome.passed(
                "No base and no in-tree baseline -- first-adoption bootstrap pass"
            )
        return Outcome.failed(
            "FAIL: cannot resolve merge-base (origin/main unfetched or stale) "
            "with an in-tree baseline present; fetch origin/main or pass --base-ref"
        )

    def _absent_base_baseline(self) -> Outcome:
        """Decide the verdict when the base commit carries no baseline blob.

        Matches the OO ratchet's ``_absent_base_baseline`` exactly (no
        ``require_base`` param): genuine first-adoption requires the
        ``origin/main`` tip to also lack a baseline. If the tip is unresolvable
        with an in-tree baseline present, first-adoption cannot be confirmed --
        fail closed unconditionally. If the tip carries a baseline, the branch
        forked before adoption and would launder a regression -- fail closed.
        """
        tip = self._git.resolve_ref("origin/main")
        if tip is None:
            if self._baseline.exists:
                return Outcome.failed(
                    "FAIL: base has no baseline and origin/main is unresolvable "
                    "with an in-tree baseline present; fetch origin/main"
                )
            return Outcome.passed(
                "No base baseline and no origin/main -- first-adoption bootstrap pass"
            )
        if self._git.show_baseline(tip) is not None:
            return Outcome.failed(
                "FAIL: base commit predates baseline adoption; rebase onto current main"
            )
        return Outcome.passed(
            "No baseline at base or origin/main tip -- first-adoption bootstrap pass"
        )

    @staticmethod
    def _empty_baseline() -> Outcome:
        """Fail closed on an empty ``{}`` base baseline under ``--require-base``.

        A truncated write or a bad merge can empty the baseline; every touched
        file would then look new. Under ``--require-base`` fail closed, exactly
        like a missing baseline. Without ``--require-base`` the empty baseline
        flows through ``_check_against`` instead (see ``check``), so the
        touched-file parse check still runs -- matching the OO ratchet.
        """
        return Outcome.failed(
            "FAIL: base coupling baseline is empty (truncated write or bad "
            "merge) and --require-base is set"
        )

    def _build_reviews(
        self,
        touched: list[str],
        current: dict[str, dict[str, float]],
        baseline: dict[str, dict[str, float]],
        renames: dict[str, str],
        waivable: frozenset[tuple[str, str]],
    ) -> tuple[CouplingReview, ...]:
        reviews: list[CouplingReview] = []
        for path in touched:
            cur = current.get(path)
            if cur is None:
                continue
            base_entry = baseline.get(path)
            if base_entry is None and path in renames:
                base_entry = baseline.get(renames[path])
            intree = self._baseline.get(path)
            reviews.append(CouplingReview(path, cur, base_entry, intree, waivable))
        return tuple(reviews)

    def _verdict(self, reviews: tuple[CouplingReview, ...]) -> Outcome:
        rows = tuple(row for review in reviews for row in review.rows)
        regressions = tuple((r.path, metric) for r in reviews for metric in r.regressed)
        lines = self._render_rows(rows)
        if regressions:
            lines.append("\nFAIL: regression detected")
            lines.extend(f"  {path}: {metric}" for path, metric in regressions)
            return Outcome(1, tuple(lines))
        lines.append("\nPASS: no regressions")
        return Outcome(0, tuple(lines))

    @staticmethod
    def _render_rows(rows: tuple[Row, ...]) -> list[str]:
        lines = [_HEADER, "-" * 108]
        lines.extend(row.render() for row in rows)
        if not rows:
            lines.append("  (all metrics unchanged)")
        return lines
