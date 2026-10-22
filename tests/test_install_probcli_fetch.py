"""install.sh's ProB download: bounded retries, HTTPS only, SHA-256 pinned.

The ProB archive host is a single university server that has dropped
connections and gone fully unreachable. ``install_probcli`` therefore runs
curl with bounded retries -- a single dropped connection recovers, a
sustained outage exits nonzero within minutes -- and verifies the archive
against a per-OS SHA-256 pin before reading anything inside it.

These tests run the shipped ``install_probcli`` function itself, not a copy:
the text from ``PROB_VERSION=`` through the function's closing ``)`` is
sliced out of install.sh and sourced under ``sh``, with a stub ``curl`` first
on PATH. No network is touched. The stub records every argv it receives and
either refuses the connection or serves a locally built ProB-shaped archive
whose probcli prints the pinned version, so the whole install -- verify,
list, extract, run -- is exercised offline. The only edit to the slice is the
pin value for the running OS, swapped for the fixture's real hash; every
other line runs as shipped.
"""

from __future__ import annotations

import hashlib
import io
import os
import platform
import re
import stat
import subprocess
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import pytest

from tests import install_sh_source

_IS_MACOS: Final[bool] = platform.system() == "Darwin"
_PIN_VAR: Final[str] = "PROB_SHA256_MACOS" if _IS_MACOS else "PROB_SHA256_LINUX"
_ARCHIVE_NAME: Final[str] = "ProB.macos.zip" if _IS_MACOS else "ProB.linux64.tar.gz"

# Fixed flag -> value pairs every ProB fetch must carry (None: no value).
EXPECTED_FLAGS: Final[dict[str, str | None]] = {
    "-fL": None,
    "--proto": "=https",
    "--proto-redir": "=https",
    "--connect-timeout": "20",
    "--retry": "5",
    "--retry-connrefused": None,
    "--retry-max-time": "300",
    "--speed-limit": "1024",
    "--speed-time": "60",
}

# CURL_MODE=modern: a curl >= 7.71 that accepts --retry-all-errors.
# CURL_MODE=old: a real pre-7.71 curl -- ANY invocation carrying
#   --retry-all-errors dies with exit 2 before doing anything, exactly as
#   curl 7.68 does; a bare --version still succeeds.
# FETCH=refuse: every download fails with curl's own "couldn't connect" (7).
# FETCH=serve: the download copies $FIXTURE to the -o path.
_STUB_CURL: Final[str] = """#!/bin/sh
printf '%s\\n' "$*" >> "$CURL_LOG"
for arg in "$@"; do
  if [ "$CURL_MODE" = old ] && [ "$arg" = "--retry-all-errors" ]; then
    echo "curl: option --retry-all-errors: is unknown" >&2
    echo "curl: try 'curl --help' for more information" >&2
    exit 2
  fi
done
for arg in "$@"; do
  if [ "$arg" = "--version" ]; then
    echo "curl 7.68.0 (x86_64-pc-linux-gnu) libcurl/7.68.0 (stub)"
    exit 0
  fi
done
out=""
while [ $# -gt 0 ]; do
  if [ "$1" = "-o" ]; then out="$2"; shift; fi
  shift
done
if [ "$FETCH" = serve ]; then
  cp "$FIXTURE" "$out"
  exit 0
fi
echo "curl: (7) Failed to connect to stub host" >&2
exit 7
"""


def _fake_probcli() -> bytes:
    version = install_sh_source.prob_version()
    return f"#!/bin/sh\necho 'ProB command line, version {version}'\n".encode()


def _fixture_archive(directory: Path) -> Path:
    """Build a ProB-shaped archive whose probcli reports the pinned version."""
    path = directory / _ARCHIVE_NAME
    if _IS_MACOS:
        with zipfile.ZipFile(path, "w") as zf:
            zinfo = zipfile.ZipInfo("ProB/probcli")
            zinfo.external_attr = 0o755 << 16
            zf.writestr(zinfo, _fake_probcli())
    else:
        with tarfile.open(path, "w:gz") as tf:
            tinfo = tarfile.TarInfo("ProB/probcli")
            tinfo.size = len(_fake_probcli())
            tinfo.mode = 0o755
            tf.addfile(tinfo, io.BytesIO(_fake_probcli()))
    return path


@dataclass(frozen=True, slots=True)
class Run:
    """One sourced run of install_probcli: its outcome and every curl argv."""

    result: subprocess.CompletedProcess[str]
    calls: list[list[str]]
    home: Path

    def fetch(self) -> list[str]:
        fetches = [c for c in self.calls if "-o" in c]
        assert len(fetches) == 1, f"expected exactly one ProB fetch, got {self.calls!r}"
        return fetches[0]


def run_install_probcli(
    tmp_path: Path, *, curl_mode: str, fetch: str, pin: str | None = None
) -> Run:
    """Source and run install_probcli; ``pin`` replaces this OS's shipped pin.

    ``pin`` is None to run the shipped (placeholder) pin unmodified.
    """
    stub_dir = tmp_path / "bin"
    stub_dir.mkdir()
    stub = stub_dir / "curl"
    stub.write_text(_STUB_CURL, encoding="utf-8")
    stub.chmod(stub.stat().st_mode | stat.S_IXUSR)
    source = install_sh_source.install_probcli_source()
    if pin is not None:
        shipped = f'{_PIN_VAR}="{install_sh_source.pins()[_PIN_VAR]}"'
        assert shipped in source, f"{_PIN_VAR} assignment not inside the slice"
        source = source.replace(shipped, f'{_PIN_VAR}="{pin}"')
    funcs = tmp_path / "funcs.sh"
    funcs.write_text(source, encoding="utf-8")
    home = tmp_path / "home"
    home.mkdir()
    log = tmp_path / "curl.log"
    fixture_dir = tmp_path / "fixture"
    fixture_dir.mkdir()
    env = {
        "HOME": str(home),
        # Stub first; system dirs supply file/tar/unzip/sha256sum/shasum. No
        # probcli is on this PATH and PROBCLI is unset, so the
        # already-installed shortcut cannot skip the download under test.
        "PATH": f"{stub_dir}{os.pathsep}/usr/bin{os.pathsep}/bin",
        "CURL_LOG": str(log),
        "CURL_MODE": curl_mode,
        "FETCH": fetch,
        "FIXTURE": str(_fixture_archive(fixture_dir)),
    }
    result = subprocess.run(
        ["sh", "-c", '. "$1"; install_probcli', "sh", str(funcs)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    lines = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    return Run(result, [ln.split() for ln in lines], home)


def _fixture_sha256(tmp_path: Path) -> str:
    scratch = tmp_path / "hash-src"
    scratch.mkdir()
    return hashlib.sha256(_fixture_archive(scratch).read_bytes()).hexdigest()


def _flag_pairs(argv: list[str]) -> dict[str, str | None]:
    pairs: dict[str, str | None] = {}
    for flag, value in EXPECTED_FLAGS.items():
        assert flag in argv, f"ProB fetch lost {flag}: {argv}"
        pairs[flag] = None if value is None else argv[argv.index(flag) + 1]
    return pairs


def test_slice_ends_inside_the_installer() -> None:
    source = install_sh_source.install_probcli_source()
    assert source.startswith("PROB_VERSION=")
    assert source.rstrip().endswith(")")


@pytest.mark.parametrize("curl_mode", ["modern", "old"])
def test_fetch_carries_https_only_and_bounded_retry_flags(
    tmp_path: Path, curl_mode: str
) -> None:
    run = run_install_probcli(tmp_path, curl_mode=curl_mode, fetch="refuse")
    assert _flag_pairs(run.fetch()) == EXPECTED_FLAGS


def test_modern_curl_also_retries_all_errors(tmp_path: Path) -> None:
    run = run_install_probcli(tmp_path, curl_mode="modern", fetch="refuse")
    assert "--retry-all-errors" in run.fetch()
    assert "predates --retry-all-errors" not in run.result.stderr


def test_old_curl_downloads_without_the_unknown_option_and_warns(
    tmp_path: Path,
) -> None:
    # A pre-7.71 curl rejects --retry-all-errors outright, so a probe that
    # does not actually pass the option would hand it to the fetch and turn
    # every install on such a system into "option is unknown".
    run = run_install_probcli(
        tmp_path, curl_mode="old", fetch="serve", pin=_fixture_sha256(tmp_path)
    )

    assert "--retry-all-errors" not in run.fetch()
    assert "curl 7.68.0" in run.result.stderr
    assert "predates --retry-all-errors" in run.result.stderr
    assert run.result.returncode == 0, run.result.stderr


def test_sustained_failure_fails_loudly(tmp_path: Path) -> None:
    run = run_install_probcli(tmp_path, curl_mode="modern", fetch="refuse")

    assert run.result.returncode != 0
    assert "download failed: https://stups.hhu-hosting.de/" in run.result.stderr
    assert "Failed to connect" in run.result.stderr


def test_matching_pin_installs_and_runs_probcli(tmp_path: Path) -> None:
    run = run_install_probcli(
        tmp_path, curl_mode="modern", fetch="serve", pin=_fixture_sha256(tmp_path)
    )

    assert run.result.returncode == 0, run.result.stderr
    assert "probcli" in run.result.stdout
    assert (run.home / "Applications" / "ProB" / "probcli").is_file()


def test_mismatched_pin_fails_before_extraction(tmp_path: Path) -> None:
    wrong = "0" * 64
    run = run_install_probcli(tmp_path, curl_mode="modern", fetch="serve", pin=wrong)
    actual = _fixture_sha256(tmp_path)

    err = run.result.stderr
    assert run.result.returncode != 0
    assert "SHA-256 mismatch" in err
    assert f"expected: {wrong}" in err
    assert f"actual:   {actual}" in err
    assert _ARCHIVE_NAME in err
    assert "https://stups.hhu-hosting.de/" in err
    # Nothing was unpacked, and the unverified archive was not left behind.
    assert not (run.home / "Applications" / "ProB" / "probcli").exists()
    assert not (run.home / "Applications" / _ARCHIVE_NAME).exists()


@pytest.mark.parametrize(
    "pin", ["PLACEHOLDER-unverified", "", "A" * 64, "0" * 63, "0" * 65]
)
def test_non_hash_pin_fails_closed(tmp_path: Path, pin: str) -> None:
    # A placeholder, an empty value, uppercase, or a wrong length must never
    # be read as "skip verification".
    run = run_install_probcli(tmp_path, curl_mode="modern", fetch="serve", pin=pin)

    assert run.result.returncode != 0
    assert ("no verified SHA-256 pin" in run.result.stderr) or (
        "SHA-256 mismatch" in run.result.stderr
    )
    assert not (run.home / "Applications" / "ProB" / "probcli").exists()


def test_shipped_pins_are_hashes_or_fail_closed_placeholders() -> None:
    for name, value in install_sh_source.pins().items():
        assert re.fullmatch(r"[0-9a-f]{64}", value) or value.startswith(
            "PLACEHOLDER-"
        ), f"install.sh {name} is neither a SHA-256 nor a marked placeholder: {value!r}"
