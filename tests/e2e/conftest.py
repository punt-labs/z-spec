"""Provision isolated state for installed-wheel subprocesses."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def z_spec() -> str:
    """Resolve the required installed CLI."""
    executable = os.environ.get("Z_SPEC_TEST_EXECUTABLE")
    if executable is None:
        tool_dir = subprocess.check_output(
            ["uv", "tool", "dir", "--bin"], text=True, timeout=10
        ).strip()
        executable = str(Path(tool_dir) / "z-spec")
    binary = shutil.which(executable)
    if binary is None:
        pytest.fail("Run `make install` and then `make test-e2e` against that wheel")
    return binary


@pytest.fixture
def child_env(private_home: Path, tmp_path: Path) -> dict[str, str]:
    """Supply only the necessary tool and sandbox settings to children."""
    return {
        "PATH": os.environ["PATH"],
        "HOME": str(private_home),
        "TMPDIR": str(tmp_path),
        "GIT_CONFIG_NOSYSTEM": "1",
        "LUX_SOCKET": str(tmp_path / "unserved.sock"),
        "PUNT_TELEMETRY": "off",
    }


@pytest.fixture
def spec(tmp_path: Path, child_env: dict[str, str]) -> Path:
    """Copy a real spec into a temporary enabled Git project with fuzz."""
    fuzz = shutil.which("fuzz")
    if fuzz is None:
        pytest.fail("fuzz is not installed — run `./install.sh --fuzz-only` first")
    child_env["FUZZ"] = fuzz
    project = tmp_path / "project"
    project.mkdir()
    subprocess.run(
        ["git", "init", "--quiet"],
        cwd=project,
        env=child_env,
        check=True,
        timeout=10,
    )
    marker = project / ".punt-labs/z-spec/enabled"
    marker.parent.mkdir(parents=True)
    marker.touch()
    source = Path(__file__).resolve().parents[2] / "examples/animation-hints-good.tex"
    return Path(shutil.copyfile(source, project / source.name))
