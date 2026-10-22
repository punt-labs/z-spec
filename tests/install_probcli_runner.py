"""Run install.sh's shipped install_probcli offline, with every tool observed.

The text from ``PROB_VERSION=`` through the function's closing ``)`` is
sliced out of install.sh and sourced under ``sh``; the only edit is the pin
value for the archive's OS, plus any edits a scenario names. It is called
exactly as install.sh calls it -- ``run_errexit install_probcli`` -- so set
-e is in force in the tests as in a real install, and both take the same
path through every handler. PATH is a directory built per run holding only
the tools the function needs, so a scenario can take a hash tool away.
``uname`` there reports the OS the scenario's archive is for, so both of
install_probcli's archive branches -- the macOS zip (unzip) and the Linux
tar.gz (tar) -- run on every host, each with the host's own unzip and tar.
``curl`` there is a stub (``install_probcli_stubs``) that records every
argv and refuses, serves a locally built ProB-shaped archive, or dies
mid-transfer; ``tar`` and ``unzip`` are logging wrappers around the real
tools, so a test can prove an archive was never listed or extracted. Every
stub logs through ``stub_log.StubLog``, so an empty argument or one
containing a space reaches the test exactly as install_probcli passed it.
No network is touched.
"""

from __future__ import annotations

import platform
import shutil
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal, final

import pytest

from tests import install_probcli_stubs as stubs
from tests.install_sh_source import CurlFlags, InstallSh
from tests.prob_archive import ProbArchive
from tests.stub_log import StubLog

SYSTEM: Final[str] = platform.system()
# Both archive formats, as `uname -s` names the OS each is for.
SYSTEMS: Final[tuple[str, ...]] = ("Linux", "Darwin")
_PIN_VARS: Final[dict[str, str]] = {
    "Linux": "PROB_SHA256_LINUX",
    "Darwin": "PROB_SHA256_MACOS",
}
VERSION: Final[str] = InstallSh().prob_version()
GOOD: Final[ProbArchive] = ProbArchive.with_probcli(SYSTEM, VERSION)
HOST_URL: Final[str] = "https://stups.hhu-hosting.de/"
# How install.sh calls install_probcli, with its status as the run's own.
_CALL: Final[str] = '. "$1"; run_errexit install_probcli; exit "$RUN_ERREXIT_RC"'

type HomeMode = Literal["absolute", "relative", "unset"]

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
    "tr",
)
_LOGGED: Final[tuple[str, ...]] = ("tar", "unzip")


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
    """One sourced run of install_probcli: its outcome and every tool call.

    Output is decoded as UTF-8 with surrogateescape, so a byte that is not
    UTF-8 reaches a test as a lone surrogate instead of failing the decode.
    """

    result: subprocess.CompletedProcess[str]
    home: Path
    logs: Path
    archive_name: str  # ProB.linux64.tar.gz or ProB.macos.zip

    def calls(self, tool: str) -> list[list[str]]:
        """Return every logged argv of ``tool``, argument boundaries intact."""
        return StubLog(self.logs).calls(tool)

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
        """Every tar/unzip call the failing-extractor stub would fail."""
        return [c for c in self.archive_reads() if StubLog.is_extraction(c)]

    def installed(self) -> bool:
        return (self.home / "Applications" / "ProB" / "probcli").exists()

    def archive_left(self) -> bool:
        return (self.home / "Applications" / self.archive_name).exists()

    def escaped(self) -> bool:
        """Whether an archive member named "escaped" landed anywhere."""
        return any(
            p.exists()
            for p in (self.home / "escaped", self.home / "Applications" / "escaped")
        )


@final
@dataclass(frozen=True, slots=True)
class Scenario:
    """How to run install_probcli: curl's behaviour, the pin, the tools.

    The run takes the OS ``archive`` is for: ``uname -s`` reports it, and
    its PROB_SHA256_* pin is the one replaced. ``edits`` are (old, new)
    replacements in the sliced source, each of which must match once.
    ``refused`` names tools replaced by a stub that fails every call.
    ``env`` is added to the run's environment.
    """

    curl_mode: str = "modern"
    fetch: str = "serve"
    pin: str | None = None  # None: the shipped pin, unmodified
    archive: ProbArchive = GOOD
    hashers: tuple[str, ...] = HOST_HASHERS
    broken_hashers: bool = False
    extraction_fails: bool = False  # tar -x / unzip -oq fail, listings run
    listing_fails: bool = False  # unzip -Z1 fails; unzip -tq still runs
    home: str = "home"  # HOME, relative to the run's tmp_path
    home_mode: HomeMode = "absolute"  # relative: HOME is that relative path
    edits: tuple[tuple[str, str], ...] = ()
    refused: tuple[str, ...] = ()
    env: tuple[tuple[str, str], ...] = ()

    @classmethod
    def pinned(cls, archive: ProbArchive = GOOD) -> Scenario:
        """A run whose pin is ``archive``'s own hash."""
        return cls(pin=archive.sha256(), archive=archive)

    def run(self, tmp_path: Path) -> Run:
        funcs = tmp_path / "funcs.sh"
        funcs.write_text(self._source(), encoding="utf-8")
        home, logs = tmp_path / self.home, tmp_path / "logs"
        home.mkdir(parents=True, exist_ok=True)
        logs.mkdir()
        env = {
            # No probcli is on this PATH and PROBCLI is unset, so the
            # already-installed shortcut cannot skip the download under test.
            "PATH": str(self._bin(tmp_path / "bin")),
            "LOGS": str(logs),
            "CURL_MODE": self.curl_mode,
            "FETCH": self.fetch,
            "FIXTURE": str(self.archive.write(tmp_path / "fixture")),
            **dict(self.env),
        }
        if self.home_mode != "unset":
            env["HOME"] = str(home) if self.home_mode == "absolute" else self.home
        result = subprocess.run(
            [_real("sh"), "-c", _CALL, "sh", str(funcs)],
            env=env,
            capture_output=True,
            encoding="utf-8",
            errors="surrogateescape",
            check=False,
            timeout=60,
            cwd=tmp_path,
        )
        return Run(result, home, logs, self.archive.name)

    def _source(self) -> str:
        source = InstallSh().install_probcli_source()
        edits = list(self.edits)
        if self.pin is not None:
            var = _PIN_VARS[self.archive.system]
            shipped = f'{var}="{InstallSh().pins()[var]}"'
            edits.insert(0, (shipped, f'{var}="{self.pin}"'))
        for old, new in edits:
            if source.count(old) != 1:
                pytest.fail(f"{old!r} is not in the slice exactly once")
            source = source.replace(old, new)
        return source

    def _bin(self, bin_dir: Path) -> Path:
        bin_dir.mkdir()
        for tool in _TOOLS:
            if tool not in self.refused:
                (bin_dir / tool).symlink_to(_real(tool))
        for tool in self.refused:
            _script(bin_dir / tool, stubs.refusing(tool))
        for tool in _LOGGED:
            wrapper = StubLog.wrapper(
                tool,
                _real(tool),
                extraction_fails=self.extraction_fails,
                listing_fails=self.listing_fails,
            )
            _script(bin_dir / tool, wrapper)
        for tool in self.hashers:
            if self.broken_hashers:
                _script(bin_dir / tool, stubs.broken_hasher(tool))
            else:
                (bin_dir / tool).symlink_to(_real(tool))
        _script(bin_dir / "curl", stubs.CURL)
        _script(bin_dir / "uname", stubs.uname(self.archive.system))
        return bin_dir
