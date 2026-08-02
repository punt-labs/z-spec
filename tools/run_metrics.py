#!/usr/bin/env python3
"""ABC Metrics runner for punt-z-spec.

Measures Assignments, Branches, and Conditions per module -- a complexity
metric that catches god classes and tangled control flow better than LOC.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

# Default location; override with PYTHON_ABC_DIR env var.
_DEFAULT_ABC_DIR = Path.home() / "Coding" / "python-abc"


def run_metrics() -> None:
    """Run ABC metrics on src/punt_zspec/ and print results sorted by magnitude."""
    src_dir: Path = Path("src/punt_zspec").absolute()

    if not src_dir.is_dir():
        print(f"Error: {src_dir} not found", file=sys.stderr)
        sys.exit(1)

    python_abc_dir = Path(os.environ.get("PYTHON_ABC_DIR", str(_DEFAULT_ABC_DIR)))
    if not python_abc_dir.is_dir():
        print(
            f"python-abc not found at {python_abc_dir}\n"
            "Install: git clone https://github.com/eoinnoble/"
            "python-abc && cd python-abc && python -m venv venv "
            "&& venv/bin/pip install -e .\n"
            "Or set PYTHON_ABC_DIR to a custom location.",
            file=sys.stderr,
        )
        sys.exit(1)

    venv_python = python_abc_dir / "venv" / "bin" / "python"
    if not venv_python.is_file():
        print(
            f"python-abc venv not found at {venv_python}\n"
            f"Run: cd {python_abc_dir} && python -m venv venv "
            "&& venv/bin/pip install -e .",
            file=sys.stderr,
        )
        sys.exit(1)

    verbose = "--verbose" in sys.argv or "-v" in sys.argv

    original_dir = Path.cwd()
    os.chdir(python_abc_dir)
    try:
        cmd = [str(venv_python), "-m", "python_abc", str(src_dir), "--sort"]
        if verbose:
            cmd.append("--verbose=true")

        result = subprocess.run(
            cmd,
            check=True,
            text=True,
            capture_output=True,
        )
        pattern = re.escape(str(src_dir)) + "/?"
        output = re.sub(pattern, "./src/punt_zspec/", result.stdout)
        print(output)

        if result.stderr:
            print(result.stderr, file=sys.stderr)
    except subprocess.CalledProcessError as exc:
        if exc.stdout:
            pat = re.escape(str(src_dir)) + "/?"
            output = re.sub(pat, "./src/punt_zspec/", exc.stdout)
            print(output)
        if exc.stderr:
            print(exc.stderr, file=sys.stderr)
        sys.exit(1)
    finally:
        os.chdir(original_dir)


if __name__ == "__main__":
    run_metrics()
