"""Drive the installed ``z-spec`` binary as a subprocess.

Every other test in this suite imports ``punt_zspec`` from the working tree, so
none of them can see a packaging fault: an entry point that does not resolve, a
data file left out of the wheel, a verb that exists in the registry but never
reaches the installed CLI. These tests run the binary that ``make install`` put
in uv's tool directory, not the editable executable on the test runner's PATH.
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

import pytest

from punt_zspec import __version__
from punt_zspec.commands.registry import CAPABILITIES

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.e2e

_TIMEOUT = 60.0


def _run(
    z_spec: str, directory: Path, env: dict[str, str], *args: str
) -> subprocess.CompletedProcess[str]:
    """Run the installed CLI with ``args`` and capture its output."""
    return subprocess.run(
        [z_spec, *args],
        capture_output=True,
        text=True,
        timeout=_TIMEOUT,
        cwd=directory,
        env=env,
        check=False,
    )


def test_version_reports_the_installed_package(
    z_spec: str, tmp_path: Path, child_env: dict[str, str]
) -> None:
    result = _run(z_spec, tmp_path, child_env, "--version")

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == f"z-spec {__version__}"


def test_help_lists_every_registry_verb(
    z_spec: str, tmp_path: Path, child_env: dict[str, str]
) -> None:
    """A verb in the registry that never reaches the installed CLI is a defect.

    ``test_parity.py`` proves the in-process app matches the registry. This
    proves the packaged app does too — the two diverge when a module is missing
    from the wheel.
    """
    result = _run(z_spec, tmp_path, child_env, "--help")

    assert result.returncode == 0, result.stderr
    missing = [c.cli_verb for c in CAPABILITIES if c.cli_verb not in result.stdout]
    assert not missing, f"verbs absent from the installed CLI: {missing}"


def test_missing_spec_file_fails_without_a_traceback(
    z_spec: str, tmp_path: Path, child_env: dict[str, str]
) -> None:
    """A path that does not exist is normal input, not an internal error."""
    result = _run(z_spec, tmp_path, child_env, "check", "does-not-exist.tex")

    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert "Traceback" not in combined, combined


def test_check_type_checks_a_real_spec(
    z_spec: str, spec: Path, child_env: dict[str, str]
) -> None:
    """The installed CLI reaches fuzz and reports a clean spec as clean."""
    result = _run(z_spec, spec.parent, child_env, "check", spec.name)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == f"fuzz: {spec.name} OK"
    assert spec.with_suffix(".fuzz.json").is_file()


def test_doctor_runs_from_an_unrelated_directory(
    z_spec: str, tmp_path: Path, child_env: dict[str, str]
) -> None:
    """``doctor`` must not depend on being launched from the source tree."""
    result = _run(z_spec, tmp_path, child_env, "doctor")

    combined = result.stdout + result.stderr
    assert "Traceback" not in combined, combined
    assert "fuzz" in combined.lower()
