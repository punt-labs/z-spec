"""Command-line entry point: parse arguments and dispatch to the ratchet."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Self

from .audit import AuditError
from .baseline import BaselineError
from .gitio import GitError, GitRepo
from .outcome import Outcome
from .ratchet import Ratchet
from .scorer import Scorer
from .writer import BaselineWriter


@dataclass(frozen=True, slots=True)
class Options:
    """Parsed command-line options for one ratchet invocation."""

    src: Path
    check: bool
    update: bool
    reconcile: bool
    rebaseline: bool
    log: bool
    json: bool
    threshold: bool
    audit_completeness: bool
    relax: str | None
    justify: str
    base_ref: str | None
    require_base: bool
    allow_no_improvement: bool
    allow_ci_write: bool
    source: str | None

    @classmethod
    def parse(cls, argv: list[str] | None = None) -> Self:
        """Build options from ``argv`` (defaults to ``sys.argv``)."""
        parser = cls._build_parser()
        ns = parser.parse_args(argv)
        return cls(
            src=Path(ns.src),
            check=bool(ns.check),
            update=bool(ns.update),
            reconcile=bool(ns.reconcile),
            rebaseline=bool(ns.rebaseline),
            log=bool(ns.log),
            json=bool(ns.json),
            threshold=bool(ns.threshold),
            audit_completeness=bool(ns.audit_completeness),
            relax=ns.relax,
            justify=ns.justify or "",
            base_ref=ns.base_ref,
            require_base=bool(ns.require_base),
            allow_no_improvement=bool(ns.allow_no_improvement),
            allow_ci_write=bool(ns.allow_ci_write),
            source=ns.source,
        )

    @staticmethod
    def _build_parser() -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(
            prog="oo_score", description="OO quality scorer and baseline ratchet"
        )
        parser.add_argument("src", help="file or directory to score")
        # Exactly one action selects the operation; passing two is an argparse
        # error, not a silent first-wins pick.
        action = parser.add_mutually_exclusive_group()
        action.add_argument("--check", action="store_true", help="ratchet check")
        action.add_argument("--update", action="store_true", help="scoped update")
        action.add_argument("--reconcile", action="store_true", help="whole-tree")
        action.add_argument("--rebaseline", action="store_true", help="reset baseline")
        action.add_argument("--threshold", action="store_true", help="per-file table")
        action.add_argument(
            "--audit-completeness", action="store_true", help="whole-tree completeness"
        )
        action.add_argument("--relax", metavar="FILE", help="relax one file's baseline")
        # --log and --json are distinct views, not modifiers: each selects the
        # operation on its own, so they join the exclusive group rather than be
        # silently ignored when combined with another action.
        action.add_argument("--log", action="store_true", help="show audit history")
        action.add_argument("--json", action="store_true", help="emit JSON scores")
        parser.add_argument("--justify", default="", help="justification for --relax")
        parser.add_argument("--base-ref", metavar="REF", help="comparison base commit")
        parser.add_argument(
            "--require-base", action="store_true", help="fail if base unresolvable"
        )
        # Waive only the must-improve gate (mechanical version-bump PRs improve
        # no metric); regressions and baseline lock-in are still enforced.
        parser.add_argument(
            "--allow-no-improvement",
            action="store_true",
            help="waive the must-improve gate; still reject regressions",
        )
        parser.add_argument(
            "--allow-ci-write", action="store_true", help="permit writes under CI"
        )
        parser.add_argument("--source", metavar="REF", help="audit source (PR/bead)")
        return parser


class Cli:
    """Score the target and route the request to the ratchet or writer."""

    _opts: Options
    _git: GitRepo
    _root: Path

    def __new__(cls, options: Options) -> Self:
        self = super().__new__(cls)
        self._opts = options
        self._git = GitRepo()
        self._root = self._git.root or Path.cwd()
        return self

    def run(self) -> int:
        """Execute the requested operation and return its exit code."""
        if not self._opts.src.exists():
            return self._emit(Outcome.failed(f"Not found: {self._opts.src}"))
        scorer = Scorer(self._opts.src, self._root)
        try:
            action = self._run_action(scorer)
            outcome = action if action is not None else self._run_view(scorer)
        except (GitError, AuditError, BaselineError) as exc:
            outcome = Outcome.failed(f"FAIL: {exc}")
        return self._emit(outcome)

    @staticmethod
    def _emit(outcome: Outcome) -> int:
        for line in outcome.lines:
            print(line)
        return outcome.exit_code

    def _run_action(self, scorer: Scorer) -> Outcome | None:
        opts = self._opts
        ratchet = Ratchet(self._root, self._git)
        writer = BaselineWriter(self._root, self._git)
        if opts.check:
            return ratchet.check(
                scorer,
                base_ref=opts.base_ref,
                require_base=opts.require_base,
                allow_no_improvement=opts.allow_no_improvement,
            )
        if opts.rebaseline:
            return writer.rebaseline(
                scorer, allow_ci_write=opts.allow_ci_write, source=opts.source
            )
        if opts.reconcile:
            return writer.reconcile(
                scorer, allow_ci_write=opts.allow_ci_write, source=opts.source
            )
        if opts.relax is not None:
            return writer.relax(
                scorer,
                opts.relax,
                justify=opts.justify,
                allow_ci_write=opts.allow_ci_write,
                source=opts.source,
            )
        if opts.update:
            return writer.update(
                scorer,
                base_ref=opts.base_ref,
                require_base=opts.require_base,
                allow_ci_write=opts.allow_ci_write,
                source=opts.source,
            )
        if opts.log:
            return ratchet.show_log()
        if opts.audit_completeness:
            return ratchet.audit_completeness(scorer)
        return None

    def _run_view(self, scorer: Scorer) -> Outcome:
        code = 1 if scorer.fail_count > 0 else 0
        if self._opts.json:
            return Outcome(code, (scorer.to_json(),))
        lines = list(scorer.render_table())
        if self._opts.threshold:
            lines.extend(scorer.render_per_file())
        return Outcome(code, tuple(lines))


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and run the ratchet CLI, returning an exit code."""
    return Cli(Options.parse(argv)).run()
