#!/usr/bin/env python3
"""Test coverage runner for punt-z-spec.

Runs pytest with coverage measurement and generates terminal + HTML reports.
"""

from __future__ import annotations

import subprocess
import sys


def run_coverage() -> None:
    """Run tests with coverage and generate reports."""
    subprocess.run(["coverage", "erase"], check=True)

    result = subprocess.run(
        [
            "coverage",
            "run",
            "--source=src/punt_zspec",
            "-m",
            "pytest",
            "-q",
        ],
        check=False,
    )

    # Capture the pytest exit code so we can propagate it after reports.
    pytest_rc = result.returncode

    if pytest_rc not in (0, 5):
        print(f"Tests exited with code {pytest_rc}", file=sys.stderr)

    # Generate reports regardless of test outcome -- partial coverage
    # data is still useful for diagnosing failures.
    subprocess.run(["coverage", "report", "-m"], check=True)
    subprocess.run(["coverage", "html"], check=True)

    print("\nHTML coverage report: htmlcov/index.html")

    # Exit with the pytest return code so callers see the failure.
    if pytest_rc != 0:
        sys.exit(pytest_rc)


if __name__ == "__main__":
    run_coverage()
