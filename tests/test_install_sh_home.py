"""install.sh refuses a HOME that is not an absolute path, before anything else.

Every path the installer sources, runs, or puts on PATH hangs off $HOME. A
relative HOME resolves them against the directory the installer was started
in, so a file planted there -- an env file, a probcli, a uv -- would be
sourced or executed. The whole script is run with HOME set to the relative
path of a planted tree (``install_sh_runner``): nothing in it may be
sourced, run, or reached through PATH. ``install_probcli`` keeps its own
copy of the guard, checked through the sourced function.
"""

from __future__ import annotations

import stat
from dataclasses import replace
from pathlib import Path
from typing import Final

import pytest

from tests.install_probcli_runner import Scenario
from tests.install_sh_runner import VERSION, WholeInstall
from tests.stub_log import StubLog

_HOMES: Final[dict[str, str | None]] = {"relative": "home", "empty": "", "unset": None}


def _refusal(home: str | None) -> str:
    shown = home or ""
    return f"install.sh: HOME is not an absolute path (HOME='{shown}') -- " + (
        "refusing to run\n"
    )


@pytest.mark.parametrize("home", _HOMES.values(), ids=_HOMES.keys())
def test_whole_script_refuses_a_non_absolute_home_first(
    tmp_path: Path, home: str | None
) -> None:
    run = WholeInstall(home).run(tmp_path)
    assert run.result.returncode == 1
    # The refusal is the only output: no step before it ran.
    assert run.result.stderr == _refusal(home)
    assert run.result.stdout == ""
    assert run.logged() == [], "something ran or was sourced first"


def test_relative_home_never_sources_runs_or_puts_its_tree_on_path(
    tmp_path: Path,
) -> None:
    run = WholeInstall("home").run(tmp_path)
    assert run.calls("sourced-local-env") == [], "sourced ./home/.local/bin/env"
    assert run.calls("sourced-cargo-env") == [], "sourced ./home/.cargo/env"
    assert run.calls("home-probcli") == [], "ran ./home/Applications/ProB/probcli"
    # Each of these is found only through a PATH entry under ./home.
    for tool in ("uv", "z-spec", "fuzz"):
        assert run.calls(tool) == [], f"ran ./home/.local/bin/{tool} via PATH"
    assert run.calls("curl") == []


def test_the_home_check_precedes_argument_parsing(tmp_path: Path) -> None:
    # An unknown option is a usage error (exit 2) -- but only once HOME passed.
    run = WholeInstall("home", args=("--no-such-option",)).run(tmp_path)
    assert run.result.returncode == 1
    assert run.result.stderr == _refusal("home")


def test_an_absolute_home_is_not_refused(tmp_path: Path) -> None:
    # The control: the same planted tree, an absolute HOME, the script runs
    # on through its steps and sources the env file it is meant to.
    run = WholeInstall(str(tmp_path / "home")).run(tmp_path)
    assert "HOME is not an absolute path" not in run.result.stderr
    assert run.calls("sourced-local-env") != []
    assert run.calls("uv") != []


@pytest.mark.parametrize("home", ["home", ""], ids=["relative", "empty"])
def test_install_probcli_refuses_a_non_absolute_home(tmp_path: Path, home: str) -> None:
    run = replace(Scenario.pinned(), home=home, home_mode="relative").run(tmp_path)

    assert run.result.returncode != 0
    assert f"HOME is not an absolute path (HOME='{home}')" in run.result.stderr
    assert run.calls("curl") == [], "a relative HOME still reached the host"
    assert not (tmp_path / home / "Applications").exists()


def test_install_probcli_never_runs_a_probcli_under_a_relative_home(
    tmp_path: Path,
) -> None:
    # Checked before the already-installed shortcut, which would run
    # $PROB_HOME/probcli -- here ./home/Applications/ProB/probcli.
    planted = tmp_path / "home" / "Applications" / "ProB" / "probcli"
    planted.parent.mkdir(parents=True)
    planted.write_text(
        "#!/bin/sh\n"
        + StubLog.append_line("planted-probcli")
        + f"echo 'ProB command line, version {VERSION}'\n",
        encoding="utf-8",
    )
    planted.chmod(planted.stat().st_mode | stat.S_IXUSR)
    run = replace(Scenario.pinned(), home="home", home_mode="relative").run(tmp_path)

    assert run.result.returncode != 0
    assert run.calls("planted-probcli") == [], "ran ./home/Applications/ProB/probcli"
    assert "already" not in run.result.stdout
