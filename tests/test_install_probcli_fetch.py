"""install.sh's ProB download must retry transient failures and still fail loudly.

The ProB archive host is a single university server that has dropped
connections and gone fully unreachable. ``install_probcli`` therefore runs
curl with bounded retries: a single dropped connection recovers, a sustained
outage exits nonzero within minutes rather than hanging or passing.

These tests run the shipped ``install_probcli`` function itself, not a copy:
the text from ``PROB_VERSION=`` through the function's closing ``)`` is
sliced out of install.sh and sourced under ``sh``, with a stub ``curl`` first
on PATH. The stub records every argv it receives and fails the download, so
the tests observe both the flags actually passed and the failure path. No
network is touched.
"""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path
from typing import Final

import pytest

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
_INSTALL_SH: Final[Path] = _REPO_ROOT / "install.sh"

# The flags every ProB fetch carries, whatever the local curl's age.
_BASE_RETRY_FLAGS: Final[tuple[str, ...]] = (
    "--connect-timeout",
    "--retry",
    "--retry-connrefused",
    "--retry-max-time",
    "--speed-limit",
    "--speed-time",
)

# The stub answers the --retry-all-errors capability probe with $PROBE_RC
# (0 = a curl >= 7.71 that knows the option, 2 = an older curl rejecting it)
# and fails every real fetch with curl's own "couldn't connect" exit code.
_STUB_CURL: Final[str] = """#!/bin/sh
printf '%s\\n' "$*" >> "$CURL_LOG"
for arg in "$@"; do
  if [ "$arg" = "--version" ]; then exit "$PROBE_RC"; fi
done
echo "curl: (7) Failed to connect to stub host" >&2
exit 7
"""


def _install_probcli_source() -> str:
    lines = _INSTALL_SH.read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("PROB_VERSION="))
    opener = next(i for i, line in enumerate(lines) if line == "install_probcli() (")
    end = next(i for i in range(opener, len(lines)) if lines[i] == ")")
    return "\n".join(lines[start : end + 1]) + "\n"


def _run_install_probcli(
    tmp_path: Path, probe_rc: int
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    stub_dir = tmp_path / "bin"
    stub_dir.mkdir()
    stub = stub_dir / "curl"
    stub.write_text(_STUB_CURL, encoding="utf-8")
    stub.chmod(stub.stat().st_mode | stat.S_IXUSR)
    funcs = tmp_path / "funcs.sh"
    funcs.write_text(_install_probcli_source(), encoding="utf-8")
    home = tmp_path / "home"
    home.mkdir()
    log = tmp_path / "curl.log"
    env = {
        "HOME": str(home),
        # Stub first; system dirs supply file/tar/unzip/awk. No probcli is on
        # this PATH and PROBCLI is unset, so the already-installed shortcut
        # cannot skip the download under test.
        "PATH": f"{stub_dir}{os.pathsep}/usr/bin{os.pathsep}/bin",
        "CURL_LOG": str(log),
        "PROBE_RC": str(probe_rc),
    }
    result = subprocess.run(
        ["sh", "-c", '. "$1"; install_probcli', "sh", str(funcs)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    calls = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    return result, calls


def _fetch_call(calls: list[str]) -> list[str]:
    fetches = [c.split() for c in calls if "--version" not in c.split()]
    assert len(fetches) == 1, f"expected exactly one ProB fetch, got {calls!r}"
    return fetches[0]


@pytest.mark.parametrize("probe_rc", [0, 2])
def test_fetch_carries_bounded_retry_flags(tmp_path: Path, probe_rc: int) -> None:
    _, calls = _run_install_probcli(tmp_path, probe_rc)
    argv = _fetch_call(calls)

    missing = [flag for flag in _BASE_RETRY_FLAGS if flag not in argv]
    assert not missing, f"ProB fetch lost retry flags {missing}: {argv}"
    assert "-fL" in argv, f"ProB fetch lost -f (404 saved as archive): {argv}"
    retries = int(argv[argv.index("--retry") + 1])
    assert 1 <= retries <= 10, f"--retry must be bounded, got {retries}"
    max_time = int(argv[argv.index("--retry-max-time") + 1])
    assert 0 < max_time <= 600, f"--retry-max-time must be bounded, got {max_time}"


def test_modern_curl_also_retries_all_errors(tmp_path: Path) -> None:
    _, calls = _run_install_probcli(tmp_path, probe_rc=0)
    assert "--retry-all-errors" in _fetch_call(calls)


def test_old_curl_is_not_handed_an_unknown_option(tmp_path: Path) -> None:
    # A curl < 7.71 rejects --retry-all-errors outright; passing it anyway
    # would turn every install on such a system into a hard failure.
    _, calls = _run_install_probcli(tmp_path, probe_rc=2)
    assert "--retry-all-errors" not in _fetch_call(calls)


def test_sustained_failure_fails_loudly(tmp_path: Path) -> None:
    result, _ = _run_install_probcli(tmp_path, probe_rc=0)

    assert result.returncode != 0
    assert "download failed: https://stups.hhu-hosting.de/" in result.stderr
    assert "Failed to connect" in result.stderr
