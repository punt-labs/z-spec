"""Run the whole shipped install.sh offline, from a scratch directory.

``install_probcli_runner`` sources one function; some properties only hold
for the script end to end -- what it does before any function runs, and
what its final report prints. ``WholeInstall`` runs ``sh install.sh`` with
the run's tmp_path as the working directory, PATH set to a stub directory
alone, and a ``home`` tree planted under tmp_path whatever HOME is: an env
file to source, ``uv``/``z-spec``/``fuzz`` in ``home/.local/bin``, and a
probcli in ``home/Applications/ProB``. Each planted file logs through
``stub_log.StubLog`` when it is sourced or run, so with HOME given as the
RELATIVE path ``home``, any log at all means the installer resolved a path
against the directory it was started in. Nothing reaches the network:
``curl`` is a stub that prints nothing. With ``build``, fuzz's build tools
are stubs too, so install_fuzz runs its clone/configure/make/install steps
to their end without compiling anything.
"""

from __future__ import annotations

import shutil
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Final, final

import pytest

from tests.install_sh_source import InstallSh
from tests.stub_log import StubLog

_INSTALL_SH: Final[Path] = Path(__file__).resolve().parent.parent / "install.sh"
VERSION: Final[str] = InstallSh().prob_version()
# Real tools the script's early steps and final report call, besides sh
# builtins. Nothing that installs, fetches, or builds is among them.
_TOOLS: Final[tuple[str, ...]] = (
    "cat",
    "chmod",
    "cp",
    "cut",
    "file",
    "grep",
    "head",
    "mkdir",
    "rm",
    "sh",
    "tr",
    "uname",
)
# The uv installer pipe (curl ... | sh) gets an empty script; any other use
# of curl fails as a refused connection would.
_CURL: Final[str] = (
    "#!/bin/sh\n"
    + StubLog.append_line("curl")
    + """case "$1" in
  -LsSf) exit 0 ;;
esac
echo "curl: (7) Failed to connect to stub host" >&2
exit 7
"""
)
# `git clone <url> <dir>` leaves a configure that succeeds in <dir>; every
# other git call succeeds doing nothing.
_GIT: Final[str] = (
    "#!/bin/sh\n"
    + StubLog.append_line("git")
    + """if [ "$1" = clone ]; then
  for dest in "$@"; do :; done
  mkdir -p "$dest" || exit 1
  printf '#!/bin/sh\\nexit 0\\n' > "$dest/configure" || exit 1
  chmod +x "$dest/configure" || exit 1
fi
exit 0
"""
)
# fuzz's build preflight and steps: each logs and succeeds, building nothing.
_BUILD_TOOLS: Final[tuple[str, ...]] = ("make", "gcc", "bison", "flex", "cpp", "awk")


def _log_and_succeed(name: str) -> str:
    """A script that logs its call as ``name`` and carries on."""
    return "#!/bin/sh\n" + StubLog.append_line(name)


# Planted under the home tree: relative path -> the text written there.
_PLANTED: Final[dict[str, str]] = {
    ".local/bin/env": StubLog.append_line("sourced-local-env"),
    ".cargo/env": StubLog.append_line("sourced-cargo-env"),
    ".local/bin/uv": _log_and_succeed("uv"),
    ".local/bin/z-spec": _log_and_succeed("z-spec"),
    "Applications/ProB/probcli": _log_and_succeed("home-probcli")
    + f"echo 'ProB command line, version {VERSION}'\n",
}


def _executable(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


@final
@dataclass(frozen=True, slots=True)
class WholeRun:
    """One run of install.sh: its outcome and every planted file's log.

    Output is decoded as UTF-8 with surrogateescape, so a byte that is not
    UTF-8 reaches a test as a lone surrogate instead of failing the decode.
    """

    result: subprocess.CompletedProcess[str]
    logs: Path

    def calls(self, name: str) -> list[list[str]]:
        """Every logged call of a stub or planted file, by its log name."""
        return StubLog(self.logs).calls(name)

    def logged(self) -> list[str]:
        """The names of everything that logged at all."""
        return sorted(p.name for p in self.logs.iterdir())


@final
@dataclass(frozen=True, slots=True)
class WholeInstall:
    """install.sh, run end to end against the planted home tree.

    ``home`` is HOME verbatim (``None``: unset), the planted tree being
    ``tmp_path / "home"`` either way. ``probcli`` is the shell body of a
    probcli placed in ``home/.local/bin``, which the installer finds on PATH
    once it has put that directory there; ``None`` leaves none. ``fuzz`` is
    the shell body of the fuzz planted there (``None``: one that succeeds).
    ``tmpdir`` is TMPDIR verbatim, created under tmp_path unless it is
    already there (a test may make it a symlink); ``None`` is
    ``tmp_path / "tmp"``.
    """

    home: str | None  # None: HOME is unset
    args: tuple[str, ...] = ("--no-plugin",)
    probcli: str | None = None  # None: no probcli on PATH
    fuzz: str | None = None  # None: a fuzz that logs and succeeds
    build: bool = False
    tmpdir: str | None = None  # None: an absolute TMPDIR under tmp_path

    def run(self, tmp_path: Path) -> WholeRun:
        tree, logs = tmp_path / "home", tmp_path / "logs"
        for relative, text in _PLANTED.items():
            _executable(tree / relative, text)
        fuzz = _log_and_succeed("fuzz") + (self.fuzz or "")
        _executable(tree / ".local/bin/fuzz", fuzz + "\n")
        if self.probcli is not None:
            body = _log_and_succeed("path-probcli") + self.probcli
            _executable(tree / ".local/bin/probcli", body + "\n")
        logs.mkdir()
        tmpdir = self.tmpdir or str(tmp_path / "tmp")
        (tmp_path / tmpdir).mkdir(parents=True, exist_ok=True)
        env = {
            "PATH": str(self._bin(tmp_path / "bin")),
            "LOGS": str(logs),
            "TMPDIR": tmpdir,
        }
        if self.home is not None:
            env["HOME"] = self.home
        result = subprocess.run(
            [self._real("sh"), str(_INSTALL_SH), *self.args],
            env=env,
            capture_output=True,
            encoding="utf-8",
            errors="surrogateescape",
            check=False,
            timeout=60,
            cwd=tmp_path,
        )
        return WholeRun(result, logs)

    def _bin(self, bin_dir: Path) -> Path:
        bin_dir.mkdir()
        for tool in _TOOLS:
            (bin_dir / tool).symlink_to(self._real(tool))
        _executable(bin_dir / "curl", _CURL)
        if self.build:
            (bin_dir / "mktemp").symlink_to(self._real("mktemp"))
            _executable(bin_dir / "git", _GIT)
            for tool in _BUILD_TOOLS:
                _executable(bin_dir / tool, _log_and_succeed(tool) + "exit 0\n")
        return bin_dir

    @staticmethod
    def _real(tool: str) -> str:
        found = shutil.which(tool)
        if found is None:
            pytest.fail(f"the host has no {tool}, which install.sh needs here")
        return found
