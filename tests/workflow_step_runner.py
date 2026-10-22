"""Run a specs-job step's shipped ``run:`` block offline, as GitHub would.

Text checks prove where a command sits; they cannot prove what a step does
with a hostile archive. ``StepHarness`` runs the block itself under
``bash -e`` -- how GitHub runs a ``run:`` with no ``shell:``, which a
structural test pins -- with the runner's environment supplied and a stub
directory first on a minimal PATH (``/usr/bin:/bin`` after it, nothing from
the host's own PATH). ``curl`` there serves a local archive or refuses, and
``tar``/``unzip``/``shasum`` log every call before running the real tool, so a
test can prove a rejected archive was never listed or extracted. Every stub
logs through ``stub_log.StubLog``, so an empty argument or one containing a
space reaches the test exactly as the step passed it.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from dataclasses import KW_ONLY, dataclass
from pathlib import Path
from typing import Final, Self, final

import pytest

from tests.prob_archive import ProbArchive
from tests.stub_log import StubLog
from tests.workflow_source import Workflow

SYSTEM_PATH: Final[str] = os.pathsep.join(("/usr/bin", "/bin"))
PROB_VERSION: Final[str] = Workflow().job_env("specs", "PROB_VERSION")
CACHE_KEY: Final[str] = f"prob-archive-Linux-{PROB_VERSION}-stub"
PIN_VARS: Final[dict[str, str]] = {
    "Linux": "PROB_SHA256_LINUX",
    "Darwin": "PROB_SHA256_MACOS",
}
# Pins that can never verify an archive, by the name a test reports them as.
BAD_PINS: Final[dict[str, str]] = {
    "placeholder": "PLACEHOLDER-unverified-awaiting-download-from-prob-host",
    "empty": "",
    "uppercase": "A" * 64,
    "short": "0" * 63,
    "long": "0" * 65,
    "non-hex": "g" * 64,
    "two-lines": "0" * 64 + "\nnot-a-hash",
}

_CURL: Final[str] = (
    "#!/bin/sh\n"
    + StubLog.append_line("curl")
    + """out=""
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
)


def _broken(name: str) -> str:
    """A ``name`` that logs its call, then fails as an unreadable file would."""
    return (
        "#!/bin/sh\n"
        + StubLog.append_line(name)
        + f'echo "{name}: simulated read error" >&2\nexit 1\n'
    )


def _tool(name: str) -> str:
    """Return the host's ``name``; fail loudly, never fall back, if absent."""
    found = shutil.which(name)
    if found is None:
        pytest.fail(f"the host has no {name}, which this specs step needs")
    return found


@final
@dataclass(frozen=True, slots=True)
class StepRun:
    """One execution of a specs step: its outcome and every logged tool call."""

    result: subprocess.CompletedProcess[str]
    root: Path

    @property
    def runner_temp(self) -> Path:
        return self.root / "runner"

    def calls(self, tool: str) -> list[list[str]]:
        """Return every logged argv of ``tool``, argument boundaries intact."""
        return StubLog(self.root / "logs").calls(tool)

    def archive_reads(self) -> list[list[str]]:
        """Every tar/unzip call: a list, test, or extraction of the archive."""
        return self.calls("tar") + self.calls("unzip")

    def extractions(self) -> list[list[str]]:
        """Every tar/unzip call the failing-extractor stub would fail."""
        return [c for c in self.archive_reads() if StubLog.is_extraction(c)]

    def file(self, name: str) -> str:
        """Return a runner file (github_env, github_output), or "" if unwritten."""
        path = self.runner_temp / name
        return path.read_text(encoding="utf-8") if path.exists() else ""


@final
@dataclass(frozen=True, slots=True)
class StepHarness:
    """A specs step to run: its name, its env, and the executables to stub.

    ``stubs`` maps a command name to the text of a script placed first on
    PATH. ``RUNNER_TEMP``, ``GITHUB_ENV``, ``GITHUB_OUTPUT`` and ``LOGS`` are
    supplied per run. With ``system_path`` off, PATH is the stub directory
    alone, so nothing installed on the host can be found.
    """

    step: str
    env: tuple[tuple[str, str], ...]
    stubs: tuple[tuple[str, str], ...] = ()
    system_path: bool = True

    @classmethod
    def verify(cls, probcli: str, *, fuzz: bool = True) -> Self:
        """The verify step, with a ``probcli`` whose shell body is given.

        Without the ``fuzz`` stub the PATH is the stub directory alone, so a
        fuzz the host happens to have in /usr/bin or /bin is never found.
        """
        stubs = [("probcli", f"#!/bin/sh\n{probcli}\n")]
        if fuzz:
            stubs.append(("fuzz", "#!/bin/sh\nexit 0\n"))
        env = (("PROB_VERSION", PROB_VERSION), ("PROBCLI", "probcli"))
        return cls("Verify both binaries resolve", env, tuple(stubs), system_path=fuzz)

    @classmethod
    def select(cls, runner_os: str, pins: dict[str, str]) -> Self:
        """The pin-selection step on ``runner_os`` with the given job pins."""
        env = (("PROB_VERSION", PROB_VERSION), ("RUNNER_OS", runner_os))
        return cls("Select this OS's ProB archive and pin", (*env, *pins.items()))

    def run(self, tmp_path: Path) -> StepRun:
        _, step = Workflow().step("specs", f"name: {self.step}")
        script = tmp_path / "step.sh"
        script.write_text("\n".join(step.script()) + "\n", encoding="utf-8")
        bin_dir, runner = tmp_path / "bin", tmp_path / "runner"
        for directory in (bin_dir, runner, tmp_path / "logs"):
            directory.mkdir(parents=True, exist_ok=True)
        for name, text in self.stubs:
            path = bin_dir / name
            path.write_text(text, encoding="utf-8")
            path.chmod(path.stat().st_mode | stat.S_IXUSR)
        search = [str(bin_dir), SYSTEM_PATH] if self.system_path else [str(bin_dir)]
        env = {
            **dict(self.env),
            "PATH": os.pathsep.join(search),
            "RUNNER_TEMP": str(runner),
            "GITHUB_ENV": str(runner / "github_env"),
            "GITHUB_OUTPUT": str(runner / "github_output"),
            "GITHUB_REPOSITORY": "punt-labs/z-spec",
            "LOGS": str(tmp_path / "logs"),
        }
        result = subprocess.run(
            [_tool("bash"), "-e", str(script)],
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        return StepRun(result, tmp_path)


@final
@dataclass(frozen=True, slots=True)
class InstallStep:
    """One run of the "Install probcli" step against a fixture archive.

    ``archive`` is what the restored cache holds (``cached``) or what the
    host serves on a miss; ``pin`` is the prob-pin step's sha256 output and
    ``archive_name`` its archive output. ``extraction_fails`` makes the
    tar/unzip stubs fail every extracting call while listings still run the
    real tool (``StubLog.wrapper``), so a verified archive reaches the
    extractor and the extractor fails -- for any uid, root included.
    ``listing_fails`` makes ``unzip -Z1`` fail while ``unzip -tq`` still runs,
    so a good zip passes its integrity test and only its listing fails.
    """

    archive: ProbArchive
    pin: str
    _: KW_ONLY
    cache_hit: bool = False
    cached: bool = False
    fetch: str = "serve"
    broken_shasum: bool = False
    extraction_fails: bool = False
    listing_fails: bool = False
    # None: the archive's own name, as the prob-pin step would output it.
    archive_name: str | None = None

    @classmethod
    def pinned(cls, archive: ProbArchive, *, cache_hit: bool) -> Self:
        """A run whose pin is ``archive``'s own hash, cached on a hit."""
        return cls(archive, archive.sha256(), cache_hit=cache_hit, cached=cache_hit)

    def run(self, tmp_path: Path) -> StepRun:
        if self.cached:
            self.archive.write(tmp_path / "runner" / "prob-archive")
        name = self.archive.name if self.archive_name is None else self.archive_name
        env = (
            ("PROB_VERSION", PROB_VERSION),
            ("ARCHIVE", name),
            ("EXPECTED_SHA256", self.pin),
            ("CACHE_HIT", "true" if self.cache_hit else "false"),
            ("CACHE_KEY", CACHE_KEY),
            ("FETCH", self.fetch),
            ("FIXTURE", str(self.archive.write(tmp_path / "served"))),
        )
        return StepHarness("Install probcli", env, self._stubs()).run(tmp_path)

    def _stubs(self) -> tuple[tuple[str, str], ...]:
        stubs = {"curl": _CURL}
        for name in ("tar", "unzip"):
            stubs[name] = StubLog.wrapper(
                name,
                _tool(name),
                extraction_fails=self.extraction_fails,
                listing_fails=self.listing_fails,
            )
        stubs["shasum"] = (
            _broken("shasum")
            if self.broken_shasum
            else StubLog.wrapper("shasum", _tool("shasum"))
        )
        return tuple(stubs.items())
