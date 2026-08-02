"""Drive the installed ``z-spec`` binary as a subprocess.

Every other test in this suite imports ``punt_zspec`` from the working tree, so
none of them can see a packaging fault: an entry point that does not resolve, a
data file left out of the wheel, a verb that exists in the registry but never
reaches the installed CLI. These tests run the binary that ``make install`` put
on ``PATH``, which is the artifact a user actually gets.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from punt_zspec.commands.registry import CAPABILITIES

pytestmark = pytest.mark.e2e

_TIMEOUT = 60.0


def _z_spec() -> str:
    """Return the installed ``z-spec`` executable, skipping if absent."""
    binary = shutil.which("z-spec")
    if binary is None:
        pytest.skip("z-spec is not installed — run `make install` first")
    return binary


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    """Run the installed CLI with ``args`` and capture its output."""
    return subprocess.run(
        [_z_spec(), *args],
        capture_output=True,
        text=True,
        timeout=_TIMEOUT,
        check=False,
    )


def test_version_reports_the_installed_package() -> None:
    result = _run("--version")

    assert result.returncode == 0, result.stderr
    assert "z-spec" in result.stdout


def test_help_lists_every_registry_verb() -> None:
    """A verb in the registry that never reaches the installed CLI is a defect.

    ``test_parity.py`` proves the in-process app matches the registry. This
    proves the packaged app does too — the two diverge when a module is missing
    from the wheel.
    """
    result = _run("--help")

    assert result.returncode == 0, result.stderr
    missing = [c.cli_verb for c in CAPABILITIES if c.cli_verb not in result.stdout]
    assert not missing, f"verbs absent from the installed CLI: {missing}"


def test_missing_spec_file_fails_without_a_traceback() -> None:
    """A path that does not exist is normal input, not an internal error."""
    result = _run("check", "does-not-exist.tex")

    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert "Traceback" not in combined, combined


def test_check_type_checks_a_real_spec(tmp_path: Path) -> None:
    """The installed CLI reaches fuzz and reports a clean spec as clean."""
    if shutil.which("fuzz") is None:
        pytest.skip("fuzz is not installed")
    spec = Path("examples/animation-hints-good.tex").resolve()
    if not spec.is_file():
        pytest.skip(f"{spec} is not present")

    result = subprocess.run(
        [_z_spec(), "check", str(spec)],
        capture_output=True,
        text=True,
        timeout=_TIMEOUT,
        cwd=tmp_path,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_doctor_runs_from_an_unrelated_directory(tmp_path: Path) -> None:
    """``doctor`` must not depend on being launched from the source tree."""
    result = subprocess.run(
        [_z_spec(), "doctor"],
        capture_output=True,
        text=True,
        timeout=_TIMEOUT,
        cwd=tmp_path,
        check=False,
    )

    combined = result.stdout + result.stderr
    assert "Traceback" not in combined, combined
    assert "fuzz" in combined.lower()
