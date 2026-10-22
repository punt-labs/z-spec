"""Run a specs-job step's shipped ``run:`` block offline, as GitHub would.

Text checks prove where a command sits; they cannot prove what a step does
with a hostile archive. ``StepHarness`` runs the block itself under
``bash -e`` -- how GitHub runs a ``run:`` with no ``shell:``, which a
structural test pins -- with the runner's environment supplied and a stub
directory first on a minimal PATH (``/usr/bin:/bin`` after it, nothing from
the host's own PATH). ``curl`` there serves a local archive or refuses, and
``tar``/``unzip``/``shasum`` log every call before running the real tool, so a
test can prove a rejected archive was never listed or extracted.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Self, final

import pytest

from tests.install_sh_source import ProbArchive
from tests.workflow_source import Workflow

SYSTEM_PATH: Final[str] = os.pathsep.join(("/usr/bin", "/bin"))
CACHE_KEY: Final[str] = "prob-archive-Linux-1.15.1-stub"

_CURL: Final[str] = """#!/bin/sh
printf '%s\\n' "$*" >> "$LOGS/curl"
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
_LOGGED: Final[str] = """#!/bin/sh
printf '%s\\n' "$*" >> "$LOGS/{name}"
exec '{real}' "$@"
"""
_BROKEN: Final[str] = """#!/bin/sh
printf '%s\\n' "$*" >> "$LOGS/{name}"
echo "{name}: simulated read error" >&2
exit 1
"""


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
        log = self.root / "logs" / tool
        lines = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
        return [ln.split() for ln in lines]

    def archive_reads(self) -> list[list[str]]:
        """Every tar/unzip call: a list, test, or extraction of the archive."""
        return self.calls("tar") + self.calls("unzip")

    def extractions(self) -> list[list[str]]:
        tar = [c for c in self.calls("tar") if c and "x" in c[0]]
        unzip = [c for c in self.calls("unzip") if c and c[0] == "-q"]
        return tar + unzip

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
    supplied per run.
    """

    step: str
    env: tuple[tuple[str, str], ...]
    stubs: tuple[tuple[str, str], ...] = ()

    @classmethod
    def verify(cls, probcli: str, *, fuzz: bool = True) -> Self:
        """The verify step, with a ``probcli`` whose shell body is given."""
        stubs = [("probcli", f"#!/bin/sh\n{probcli}\n")]
        if fuzz:
            stubs.append(("fuzz", "#!/bin/sh\nexit 0\n"))
        env = (("PROB_VERSION", Workflow().job_env("specs", "PROB_VERSION")),)
        return cls(
            "Verify both binaries resolve", (*env, ("PROBCLI", "probcli")), tuple(stubs)
        )

    @classmethod
    def select(cls, runner_os: str, pins: dict[str, str]) -> Self:
        """The pin-selection step on ``runner_os`` with the given job pins."""
        env = (("RUNNER_OS", runner_os), *pins.items())
        return cls("Select this OS's ProB archive and pin", env)

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
        env = {
            **dict(self.env),
            "PATH": f"{bin_dir}{os.pathsep}{SYSTEM_PATH}",
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
    host serves on a miss; ``pin`` is the prob-pin step's sha256 output.
    """

    archive: ProbArchive
    pin: str
    cache_hit: bool = False
    cached: bool = False
    fetch: str = "serve"
    broken_shasum: bool = False

    @classmethod
    def pinned(cls, archive: ProbArchive, *, cache_hit: bool) -> Self:
        """A run whose pin is ``archive``'s own hash, cached on a hit."""
        return cls(archive, archive.sha256(), cache_hit, cache_hit)

    def run(self, tmp_path: Path) -> StepRun:
        if self.cached:
            self.archive.write(tmp_path / "runner" / "prob-archive")
        env = (
            ("PROB_VERSION", Workflow().job_env("specs", "PROB_VERSION")),
            ("ARCHIVE", self.archive.name),
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
            stubs[name] = _LOGGED.format(name=name, real=_tool(name))
        stubs["shasum"] = (
            _BROKEN.format(name="shasum")
            if self.broken_shasum
            else _LOGGED.format(name="shasum", real=_tool("shasum"))
        )
        return tuple(stubs.items())
