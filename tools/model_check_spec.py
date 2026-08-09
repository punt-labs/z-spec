"""Model-check one Z spec through the engine and report probcli's verdict.

A thin client of ModelCheckCommand — the same command object the CLI verb and
the MCP tool resolve. It parses nothing itself: the verdict is ProbReport.ok,
decided in the engine, so every surface inherits the same answer.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from punt_zspec.commands.model_check import ModelCheckCommand
from punt_zspec.commands.options import ProbOptions
from punt_zspec.types import ProbReport


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("spec", type=Path, help="the .tex specification to check")
    parser.add_argument(
        "--setsize", type=int, default=1, help="probcli DEFAULT_SETSIZE"
    )
    parser.add_argument(
        "--max-ops",
        type=int,
        default=200,
        help="probcli MAX_OPERATIONS: transitions enumerated per operation",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300000,
        help=(
            "probcli TIME_OUT in MILLISECONDS, bounding one internal "
            "computation — not a wall clock. The whole process is capped "
            "separately and much lower; see _PROCESS_TIMEOUT_S in prob.py."
        ),
    )
    return parser.parse_args(argv)


def _print_summary(report: ProbReport) -> None:
    for check in report.checks:
        mark = "✓" if check.status.value in ("passed", "skipped") else "✗"
        print(f"  {mark} {check.name}: {check.status.value} — {check.detail}")
    print(
        f"  {report.states_analysed} states, "
        f"{report.transitions_fired} transitions, "
        f"{len(report.operations)} operations"
    )


def main(argv: list[str] | None = None) -> int:
    """Model-check the spec; return 0 when the report is ok, 1 when it is not."""
    args = _parse_args(argv)
    result = ModelCheckCommand().run(
        args.spec,
        ProbOptions(
            setsize=args.setsize, max_ops=args.max_ops, timeout_ms=args.timeout
        ),
    )
    err = result.error
    if err is not None:
        hint = f" {err.hint}" if err.hint else ""
        print(f"  ✗ {err.message}.{hint}", file=sys.stderr)
        return 1
    report = result.unwrap()
    _print_summary(report)
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
