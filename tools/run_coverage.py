#!/usr/bin/env python3
"""Test coverage runner for punt-z-spec.

Runs pytest with coverage measurement and generates terminal + HTML reports.
"""

from __future__ import annotations

import subprocess
import sys


def run_coverage() -> None:
    """Run tests with coverage and generate reports."""
    # `sys.executable -m coverage`, not the bare console script: the module then
    # always resolves from the environment running this file, so a coverage on
    # PATH from some other virtualenv can never measure a different interpreter.
    coverage = [sys.executable, "-m", "coverage"]

    subprocess.run([*coverage, "erase"], check=True)

    result = subprocess.run(
        [*coverage, "run", "--source=src/punt_zspec", "-m", "pytest", "-q"],
        check=False,
    )

    # Capture the pytest exit code so we can propagate it after reports.
    pytest_rc = result.returncode

    # Generate reports regardless of test outcome -- partial coverage
    # data is still useful for diagnosing failures.
    subprocess.run([*coverage, "report", "-m"], check=True)
    subprocess.run([*coverage, "html"], check=True)

    print("\nHTML coverage report: htmlcov/index.html")

    # Every non-zero code fails, exit 5 included: "no tests collected" is what a
    # collection error also reports, and a coverage run over zero tests measured
    # nothing (PY-BS-6). Exit with pytest's code so callers see which failure.
    if pytest_rc != 0:
        print(f"Tests exited with code {pytest_rc}", file=sys.stderr)
        sys.exit(pytest_rc)


if __name__ == "__main__":
    run_coverage()
