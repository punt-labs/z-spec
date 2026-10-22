"""Run install.sh's shipped install_probcli offline, with every tool observed.

The text from ``PROB_VERSION=`` through the function's closing ``)`` is
sliced out of install.sh and sourced under ``sh``; the only edit is the pin
value for the running OS. PATH is a directory built per run holding only
the tools the function needs, so a scenario can take a hash tool away.
``curl`` there is a stub that records every argv and refuses, serves a
locally built ProB-shaped archive, or dies mid-transfer; ``tar`` and
``unzip`` are logging wrappers around the real tools, so a test can prove an
archive was never listed or extracted. Each logged call is one record of
NUL-terminated arguments, so an empty argument or one containing a space
reaches the test exactly as install_probcli passed it. No network is touched.
"""

from __future__ import annotations

import platform
import shutil
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Final, final

import pytest

from tests.install_sh_source import CurlFlags, InstallSh
from tests.prob_archive import ProbArchive

SYSTEM: Final[str] = platform.system()
_PIN_VAR: Final[str] = (
    "PROB_SHA256_MACOS" if SYSTEM == "Darwin" else "PROB_SHA256_LINUX"
)
VERSION: Final[str] = InstallSh().prob_version()
GOOD: Final[ProbArchive] = ProbArchive.with_probcli(SYSTEM, VERSION)
HOST_URL: Final[str] = "https://stups.hhu-hosting.de/"


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
printf '%s\\0' "$@" >> "$LOGS/curl"
printf '\\n' >> "$LOGS/curl"
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
printf '%s\\0' "$@" >> "$LOGS/{name}"
printf '\\n' >> "$LOGS/{name}"
exec '{real}' "$@"
"""
_STUB_BROKEN_HASHER: Final[str] = """#!/bin/sh
echo "{name}: simulated read error" >&2
exit 1
"""


# The hash tools this host actually has: macOS may ship no sha256sum, and the
# default run must not demand one. Scenarios that remove a tool say so.
HOST_HASHERS: Final[tuple[str, ...]] = tuple(
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
        """Return every logged argv of ``tool``, argument boundaries intact."""
        log = self.logs / tool
        if not log.exists():
            return []
        *records, tail = log.read_text(encoding="utf-8").split("\0\n")
        if tail:
            pytest.fail(f"{tool} log ends in a partial record: {tail!r}")
        return [record.split("\0") for record in records]

    def fetches(self) -> list[list[str]]:
        return [c for c in self.calls("curl") if "-o" in c]

    def fetch(self) -> list[str]:
        fetches = self.fetches()
        if len(fetches) != 1:
            pytest.fail(f"expected one ProB fetch, got {self.calls('curl')}")
        return fetches[0]

    def fetch_flags(self) -> dict[str, str | None]:
        """Return every flag of the real fetch, -o <out> and the URL aside.

        All of them, not just the expected ones: an added flag (--insecure)
        is a difference.
        """
        argv = self.fetch()
        if not argv[-1].startswith(HOST_URL):
            pytest.fail(f"fetch does not end in the URL: {argv}")
        out = argv.index("-o")
        return CurlFlags.parse(argv[:out] + argv[out + 2 : -1]).as_dict()

    def archive_reads(self) -> list[list[str]]:
        """Every tar/unzip call: a list, test, or extraction of the archive."""
        return self.calls("tar") + self.calls("unzip")

    def extractions(self) -> list[list[str]]:
        tar = [c for c in self.calls("tar") if "x" in c[0]]
        unzip = [c for c in self.calls("unzip") if c[0] in ("-q", "-oq")]
        return tar + unzip

    def installed(self) -> bool:
        return (self.home / "Applications" / "ProB" / "probcli").exists()

    def archive_left(self) -> bool:
        return (self.home / "Applications" / GOOD.name).exists()

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
    archive: ProbArchive = GOOD
    hashers: tuple[str, ...] = HOST_HASHERS
    broken_hashers: bool = False
    home: str = "home"  # HOME, relative to the run's tmp_path
    absolute_home: bool = True  # False: HOME is passed as that relative path

    @classmethod
    def pinned(cls, archive: ProbArchive = GOOD) -> Scenario:
        """A run whose pin is ``archive``'s own hash."""
        return cls(pin=archive.sha256(), archive=archive)

    def run(self, tmp_path: Path) -> Run:
        source = InstallSh().install_probcli_source()
        if self.pin is not None:
            shipped = f'{_PIN_VAR}="{InstallSh().pins()[_PIN_VAR]}"'
            if shipped not in source:
                pytest.fail(f"{_PIN_VAR} assignment not inside the slice")
            source = source.replace(shipped, f'{_PIN_VAR}="{self.pin}"')
        funcs = tmp_path / "funcs.sh"
        funcs.write_text(source, encoding="utf-8")
        home, logs = tmp_path / self.home, tmp_path / "logs"
        home.mkdir(parents=True, exist_ok=True)
        logs.mkdir()
        env = {
            "HOME": str(home) if self.absolute_home else self.home,
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
            cwd=tmp_path,
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
