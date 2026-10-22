"""install.sh's ProB download: bounded retries, HTTPS only, SHA-256 pinned.

The ProB archive host is a single university server that has dropped
connections and gone fully unreachable. ``install_probcli`` therefore runs
curl with bounded retries -- a single dropped connection recovers, a
sustained outage exits nonzero within minutes -- checks the pin's format
before any download, and verifies the archive against a per-OS SHA-256 pin
before reading anything inside it.

These tests run the shipped ``install_probcli`` function itself, not a copy:
the text from ``PROB_VERSION=`` through the function's closing ``)`` is
sliced out of install.sh and sourced under ``sh``. PATH is a directory built
per run holding only the tools the function needs, so a test can take a hash
tool away. ``curl`` on it is a stub that records every argv and either
refuses the connection or serves a locally built ProB-shaped archive;
``tar`` and ``unzip`` are logging wrappers around the real tools, so a test
can prove an archive was never listed or extracted. No network is touched.
The only edit to the slice is the pin value for the running OS; every other
line runs as shipped.
"""

from __future__ import annotations

import io
import platform
import re
import shutil
import stat
import subprocess
import tarfile
import zipfile
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Final, final

import pytest

from tests.install_sh_source import CurlFlags, InstallSh, ProbArchive

_SYSTEM: Final[str] = platform.system()
_PIN_VAR: Final[str] = (
    "PROB_SHA256_MACOS" if _SYSTEM == "Darwin" else "PROB_SHA256_LINUX"
)
_VERSION: Final[str] = InstallSh().prob_version()
_GOOD: Final[ProbArchive] = ProbArchive.with_probcli(_SYSTEM, _VERSION)
_HOST: Final[str] = "https://stups.hhu-hosting.de/"

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

# Everything install_probcli (and the stubs) run, besides sh builtins. Hash
# tools are linked separately, so a scenario can leave either one out.
_TOOLS: Final[tuple[str, ...]] = (
    "cat",
    "chmod",
    "cp",
    "cut",
    "file",
    "grep",
    "gzip",
    "head",
    "mkdir",
    "rm",
    "uname",
)
_LOGGED: Final[tuple[str, ...]] = ("tar", "unzip")

# CURL_MODE=modern: a curl >= 7.71 that accepts --retry-all-errors.
# CURL_MODE=old: a real pre-7.71 curl -- ANY invocation carrying
#   --retry-all-errors dies with exit 2 before doing anything, exactly as
#   curl 7.68 does; a bare --version still succeeds.
# FETCH=refuse: every download fails with curl's own "couldn't connect" (7).
# FETCH=serve: the download copies $FIXTURE to the -o path.
# FETCH=partial: the transfer dies mid-way (18), leaving partial bytes at -o.
_STUB_CURL: Final[str] = """#!/bin/sh
printf '%s\\n' "$*" >> "$LOGS/curl"
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
if [ "$FETCH" = partial ]; then
  printf 'partial archive bytes' > "$out"
  echo "curl: (18) transfer closed with outstanding read data remaining" >&2
  exit 18
fi
echo "curl: (7) Failed to connect to stub host" >&2
exit 7
"""
_STUB_LOGGED: Final[str] = """#!/bin/sh
printf '%s\\n' "$*" >> "$LOGS/{name}"
exec '{real}' "$@"
"""
_STUB_BROKEN_HASHER: Final[str] = """#!/bin/sh
echo "{name}: simulated read error" >&2
exit 1
"""


# The hash tools this host actually has: macOS may ship no sha256sum, and the
# default run must not demand one. Scenarios that remove a tool say so.
_HOST_HASHERS: Final[tuple[str, ...]] = tuple(
    tool for tool in ("sha256sum", "shasum") if shutil.which(tool)
)


def _real(tool: str) -> str:
    found = shutil.which(tool)
    if found is None:
        pytest.fail(f"the host has no {tool}, which install_probcli needs")
    return found


def _script(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


@final
@dataclass(frozen=True, slots=True)
class Run:
    """One sourced run of install_probcli: its outcome and every tool call."""

    result: subprocess.CompletedProcess[str]
    home: Path
    logs: Path

    def calls(self, tool: str) -> list[list[str]]:
        log = self.logs / tool
        lines = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
        return [ln.split() for ln in lines]

    def fetches(self) -> list[list[str]]:
        return [c for c in self.calls("curl") if "-o" in c]

    def fetch(self) -> list[str]:
        fetches = self.fetches()
        assert len(fetches) == 1, f"expected one ProB fetch, got {self.calls('curl')}"
        return fetches[0]

    def fetch_flags(self) -> dict[str, str | None]:
        """Return every flag of the real fetch, -o <out> and the URL aside.

        All of them, not just the expected ones: an added flag (--insecure)
        is a difference.
        """
        argv = self.fetch()
        assert argv[-1].startswith(_HOST), f"fetch does not end in the URL: {argv}"
        out = argv.index("-o")
        return CurlFlags.parse(argv[:out] + argv[out + 2 : -1]).as_dict()

    def archive_reads(self) -> list[list[str]]:
        """Every tar/unzip call: a list, test, or extraction of the archive."""
        return self.calls("tar") + self.calls("unzip")

    def extractions(self) -> list[list[str]]:
        tar = [c for c in self.calls("tar") if c and "x" in c[0]]
        unzip = [c for c in self.calls("unzip") if c and c[0] in ("-q", "-oq")]
        return tar + unzip

    def installed(self) -> bool:
        return (self.home / "Applications" / "ProB" / "probcli").exists()

    def archive_left(self) -> bool:
        return (self.home / "Applications" / _GOOD.name).exists()

    def escaped(self) -> bool:
        """Whether an archive member named "escaped" landed anywhere."""
        return any(
            p.exists()
            for p in (self.home / "escaped", self.home / "Applications" / "escaped")
        )


@final
@dataclass(frozen=True, slots=True)
class Scenario:
    """How to run install_probcli: curl's behaviour, the pin, the tools."""

    curl_mode: str = "modern"
    fetch: str = "serve"
    pin: str | None = None  # None: the shipped pin, unmodified
    archive: ProbArchive = _GOOD
    hashers: tuple[str, ...] = _HOST_HASHERS
    broken_hashers: bool = False
    home: str = "home"  # HOME, relative to the run's tmp_path

    @classmethod
    def pinned(cls, archive: ProbArchive = _GOOD) -> Scenario:
        """A run whose pin is ``archive``'s own hash."""
        return cls(pin=archive.sha256(), archive=archive)

    def run(self, tmp_path: Path) -> Run:
        source = InstallSh().install_probcli_source()
        if self.pin is not None:
            shipped = f'{_PIN_VAR}="{InstallSh().pins()[_PIN_VAR]}"'
            assert shipped in source, f"{_PIN_VAR} assignment not inside the slice"
            source = source.replace(shipped, f'{_PIN_VAR}="{self.pin}"')
        funcs = tmp_path / "funcs.sh"
        funcs.write_text(source, encoding="utf-8")
        home, logs = tmp_path / self.home, tmp_path / "logs"
        home.mkdir(parents=True)
        logs.mkdir()
        env = {
            "HOME": str(home),
            # No probcli is on this PATH and PROBCLI is unset, so the
            # already-installed shortcut cannot skip the download under test.
            "PATH": str(self._bin(tmp_path / "bin")),
            "LOGS": str(logs),
            "CURL_MODE": self.curl_mode,
            "FETCH": self.fetch,
            "FIXTURE": str(self.archive.write(tmp_path / "fixture")),
        }
        result = subprocess.run(
            [_real("sh"), "-c", '. "$1"; install_probcli', "sh", str(funcs)],
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        return Run(result, home, logs)

    def _bin(self, bin_dir: Path) -> Path:
        bin_dir.mkdir()
        for tool in _TOOLS:
            (bin_dir / tool).symlink_to(_real(tool))
        for tool in _LOGGED:
            _script(bin_dir / tool, _STUB_LOGGED.format(name=tool, real=_real(tool)))
        for tool in self.hashers:
            if self.broken_hashers:
                _script(bin_dir / tool, _STUB_BROKEN_HASHER.format(name=tool))
            else:
                (bin_dir / tool).symlink_to(_real(tool))
        _script(bin_dir / "curl", _STUB_CURL)
        return bin_dir


def test_slice_ends_inside_the_installer() -> None:
    source = InstallSh().install_probcli_source()
    assert source.startswith("PROB_VERSION=")
    assert source.rstrip().endswith(")")


@pytest.mark.parametrize("curl_mode", ["modern", "old"])
def test_fetch_carries_exactly_the_https_only_bounded_retry_flags(
    tmp_path: Path, curl_mode: str
) -> None:
    # Exactly: a flag added to the real call (--insecure, -k) fails this.
    scenario = replace(Scenario.pinned(), curl_mode=curl_mode, fetch="refuse")
    expected = dict(EXPECTED_FLAGS)
    if curl_mode == "modern":
        expected["--retry-all-errors"] = None
    assert scenario.run(tmp_path).fetch_flags() == expected


def test_install_sh_flag_list_is_exactly_the_expected_pairs() -> None:
    assert InstallSh().fetch_flags().as_dict() == EXPECTED_FLAGS


def test_curl_flags_tell_swapped_values_apart() -> None:
    shipped = CurlFlags.parse(["--connect-timeout", "20", "--retry", "5"])
    swapped = CurlFlags.parse(["--connect-timeout", "5", "--retry", "20"])
    assert sorted(shipped.tokens()) == sorted(swapped.tokens())
    assert shipped.as_dict() != swapped.as_dict()


def test_curl_flags_reject_a_repeated_flag() -> None:
    with pytest.raises(ValueError, match="repeats a flag"):
        CurlFlags.parse(["--retry", "5", "--retry", "6"])


def test_modern_curl_also_retries_all_errors(tmp_path: Path) -> None:
    run = replace(Scenario.pinned(), fetch="refuse").run(tmp_path)
    assert "--retry-all-errors" in run.fetch()
    assert "predates --retry-all-errors" not in run.result.stderr


def test_old_curl_downloads_without_the_unknown_option_and_warns(
    tmp_path: Path,
) -> None:
    # A pre-7.71 curl rejects --retry-all-errors outright, so a probe that
    # does not actually pass the option would hand it to the fetch and turn
    # every install on such a system into "option is unknown".
    run = replace(Scenario.pinned(), curl_mode="old").run(tmp_path)

    assert "--retry-all-errors" not in run.fetch()
    assert "curl 7.68.0" in run.result.stderr
    assert "predates --retry-all-errors" in run.result.stderr
    assert run.result.returncode == 0, run.result.stderr


def test_sustained_failure_fails_loudly(tmp_path: Path) -> None:
    run = replace(Scenario.pinned(), fetch="refuse").run(tmp_path)

    assert run.result.returncode != 0
    assert f"download failed: {_HOST}" in run.result.stderr
    assert "Failed to connect" in run.result.stderr
    assert "could not read or hash" not in run.result.stderr


def test_interrupted_download_leaves_no_partial_archive(tmp_path: Path) -> None:
    run = replace(Scenario.pinned(), fetch="partial").run(tmp_path)

    assert run.result.returncode != 0
    assert f"download failed: {_HOST}" in run.result.stderr
    assert not run.archive_left(), "a partial download was left on disk"
    assert run.archive_reads() == []


def test_matching_pin_installs_and_runs_probcli(tmp_path: Path) -> None:
    run = Scenario.pinned().run(tmp_path)

    assert run.result.returncode == 0, run.result.stderr
    assert re.search(
        rf"✓ probcli \S+/ProB/probcli \({re.escape(_VERSION)}\)$",
        run.result.stdout,
        re.M,
    ), run.result.stdout
    assert run.installed()
    assert not run.archive_left(), "a verified archive is removed after install"


@pytest.mark.parametrize("hasher", _HOST_HASHERS)
def test_home_with_a_backslash_still_verifies(tmp_path: Path, hasher: str) -> None:
    # Given a file NAME with a backslash, sha256sum and shasum escape it and
    # prefix the hash with "\"; hashing stdin keeps the hash clean.
    run = replace(Scenario.pinned(), hashers=(hasher,), home="a\\b/home").run(tmp_path)

    assert "\\" in str(run.home)
    assert run.result.returncode == 0, run.result.stderr
    assert run.installed()


def test_mismatched_pin_fails_before_the_archive_is_read(tmp_path: Path) -> None:
    wrong = "0" * 64
    run = Scenario(pin=wrong).run(tmp_path)

    err = run.result.stderr
    assert run.result.returncode != 0
    assert "SHA-256 mismatch" in err
    assert f"expected: {wrong}" in err
    assert f"actual:   {_GOOD.sha256()}" in err
    assert _GOOD.name in err
    assert _HOST in err
    assert run.archive_reads() == [], "a mismatched archive was listed or extracted"
    assert not run.installed()
    assert not run.archive_left(), "the unverified archive was left on disk"


@pytest.mark.parametrize(
    "pin",
    [
        "PLACEHOLDER-unverified",
        "",
        "A" * 64,
        "0" * 63,
        "0" * 65,
        "g" * 64,
        "0" * 64 + "\n" + "0" * 64,
    ],
    ids=["placeholder", "empty", "uppercase", "short", "long", "non-hex", "2-lines"],
)
def test_non_hash_pin_fails_before_any_download(tmp_path: Path, pin: str) -> None:
    # A placeholder, an empty value, uppercase, or a wrong length must never
    # be read as "skip verification" -- and can never verify anything, so it
    # fails before a single request reaches the ProB host.
    run = Scenario(pin=pin).run(tmp_path)

    err = run.result.stderr
    assert run.result.returncode != 0
    assert f"no verified SHA-256 pin for {_GOOD.name}" in err
    assert f"pin is not 64 lowercase hex digits (value: {pin})" in err
    assert "SHA-256 mismatch" not in err
    assert run.calls("curl") == [], "a non-hash pin still reached curl"
    assert run.archive_reads() == []
    assert not run.installed()
    assert not run.archive_left()


def test_shipped_pin_never_installs_the_served_fixture(tmp_path: Path) -> None:
    # The shipped value, whatever it is: a placeholder today ("no verified
    # pin"), a real hash once one lands ("mismatch" against this fixture).
    # Either way the served archive is never read, installed, or kept.
    run = Scenario().run(tmp_path)

    err = run.result.stderr
    assert run.result.returncode != 0
    assert "no verified SHA-256 pin" in err or "SHA-256 mismatch" in err, err
    assert run.archive_reads() == []
    assert not run.installed()
    assert not run.archive_left()


@pytest.mark.parametrize("member", ["../escaped", "ProB/../../escaped", "/escaped"])
def test_pinned_archive_with_an_escaping_member_is_never_extracted(
    tmp_path: Path, member: str
) -> None:
    # The pin only proves the archive is the one the publisher shipped; the
    # slip guard is what stops a hostile publisher's ../ or absolute member.
    run = Scenario.pinned(ProbArchive.with_probcli(_SYSTEM, _VERSION, member)).run(
        tmp_path
    )

    assert run.result.returncode != 0
    assert "contains an absolute or ../ path -- refusing to extract" in (
        run.result.stderr
    )
    assert run.extractions() == [], f"an archive with {member!r} was extracted"
    assert not run.escaped()
    assert not run.installed()


def test_shasum_fallback_installs_when_sha256sum_is_absent(tmp_path: Path) -> None:
    run = replace(Scenario.pinned(), hashers=("shasum",)).run(tmp_path)

    assert run.result.returncode == 0, run.result.stderr
    assert run.installed()


def test_no_hash_tool_fails_before_any_download(tmp_path: Path) -> None:
    run = replace(Scenario.pinned(), hashers=()).run(tmp_path)

    assert run.result.returncode != 0
    assert "neither sha256sum nor shasum found" in run.result.stderr
    assert run.fetches() == [], "downloaded with nothing to verify it"
    assert not run.installed()


def test_failing_hash_tool_is_not_reported_as_a_mismatch(tmp_path: Path) -> None:
    run = replace(Scenario.pinned(), broken_hashers=True).run(tmp_path)

    err = run.result.stderr
    assert run.result.returncode != 0
    assert "could not read or hash" in err
    assert "SHA-256 mismatch" not in err
    assert run.archive_reads() == []
    assert not run.installed()
    assert not run.archive_left()


def test_probcli_reporting_another_version_fails(tmp_path: Path) -> None:
    other = f"{_VERSION}0"  # 1.15.10 must not pass as 1.15.1
    run = Scenario.pinned(ProbArchive.with_probcli(_SYSTEM, other)).run(tmp_path)

    assert run.result.returncode != 0
    assert f"expected probcli {_VERSION}, got: {other}" in run.result.stderr
    assert "✓ probcli" not in run.result.stdout


# The fixtures must not depend on the clock: a pin hashed from one build has
# to verify the next. The timestamps are checked where they live, in the
# headers, since two builds in the same second would agree by accident.
def test_tar_fixture_carries_no_timestamp() -> None:
    data = ProbArchive.with_probcli("Linux", _VERSION).data()
    assert data[:2] == b"\x1f\x8b"
    assert data[4:8] == b"\0\0\0\0", "gzip MTIME must be zero for a stable hash"
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
        assert [m.mtime for m in tf.getmembers()] == [0]


def test_zip_fixture_carries_a_fixed_timestamp() -> None:
    data = ProbArchive.with_probcli("Darwin", _VERSION, "ProB/x").data()
    # Local file header: signature, then mod time (bytes 10-11) and mod
    # date (12-13); 1980-01-01 00:00:00 is time 0, date 0x0021.
    assert data[:4] == b"PK\x03\x04"
    assert data[10:14] == b"\x00\x00\x21\x00"
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        assert {i.date_time for i in zf.infolist()} == {(1980, 1, 1, 0, 0, 0)}


def test_shipped_pins_are_hashes_or_fail_closed_placeholders() -> None:
    for name, value in InstallSh().pins().items():
        assert re.fullmatch(r"[0-9a-f]{64}", value) or value.startswith(
            "PLACEHOLDER-"
        ), f"install.sh {name} is neither a SHA-256 nor a marked placeholder: {value!r}"
