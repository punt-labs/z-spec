"""install_probcli runs with set -e in force, in the tests as in a real install.

POSIX ignores set -e for everything run on the left of || or &&, or in an
if condition -- at any depth, the function's own ``set -eu`` included. So
install.sh calls each installer as a plain command through ``run_errexit``,
and the runner calls install_probcli the same way. Here a ``false`` is
inserted into the sliced function: it must fail the install wherever it
lands, which it could not under ``install_probcli || ...``. Every failure
the function knows about is still handled explicitly; the one on the
success path -- the archive cannot be removed -- only warns.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import replace
from pathlib import Path
from typing import Final

import pytest

from tests.install_probcli_runner import Scenario
from tests.install_sh_source import InstallSh

_INSTALL_SH: Final[Path] = Path(__file__).resolve().parent.parent / "install.sh"
_DONE: Final[str] = '  echo "  ✓ probcli $PROB_HOME/probcli ($PROB_VERSION)"\n'
_INSERTED: Final[dict[str, tuple[str, str]]] = {
    "first-command": ("  set -eu\n", "  set -eu\n  false\n"),
    "after-verification": (_DONE, "  false\n" + _DONE),
}


@pytest.mark.parametrize("edit", _INSERTED.values(), ids=_INSERTED.keys())
def test_an_unhandled_failing_command_fails_the_install(
    tmp_path: Path, edit: tuple[str, str]
) -> None:
    run = replace(Scenario.pinned(), edits=(edit,)).run(tmp_path)

    assert run.result.returncode != 0, "an unhandled failure ran on"
    assert "✓ probcli" not in run.result.stdout


def test_an_archive_that_cannot_be_removed_after_install_only_warns(
    tmp_path: Path,
) -> None:
    run = replace(Scenario.pinned(), refused=("rm",)).run(tmp_path)

    archive = run.home / "Applications" / run.archive_name
    err = run.result.stderr
    assert run.result.returncode == 0, err
    assert "✓ probcli" in run.result.stdout
    assert f"rm: -f {archive}: Operation not permitted\n" in err
    assert f"  ! could not remove the downloaded {archive} -- delete it by hand\n" in (
        err
    )
    assert run.installed()


@pytest.mark.parametrize("name", ["install_probcli", "install_fuzz"])
def test_install_sh_calls_each_installer_through_run_errexit(name: str) -> None:
    lines = _INSTALL_SH.read_text(encoding="utf-8").splitlines()
    word = re.compile(rf"\b{name}\b")
    calls = [
        i
        for i, line in enumerate(lines)
        if word.search(line)
        and not line.lstrip().startswith("#")
        and line != f"{name}() ("
    ]
    assert [lines[i].strip() for i in calls] == [f"run_errexit {name}"]
    before, after = lines[calls[0] - 1].rstrip(), lines[calls[0] + 1].strip()
    assert not before.endswith(("||", "&&", "\\", "!")), before
    assert after.startswith('[ "$RUN_ERREXIT_RC" = 0 ] || '), after


def test_run_errexit_captures_the_status_and_restores_errexit(tmp_path: Path) -> None:
    # The caller's -e is lifted only for the call: a failing function is
    # captured, not fatal, and the caller's next failure still stops it.
    funcs = tmp_path / "funcs.sh"
    funcs.write_text(InstallSh().install_probcli_source(), encoding="utf-8")
    script = (
        'set -e; . "$1"; fails() ( set -e; false; echo ran-on-inside ); '
        'run_errexit fails; echo "rc=$RUN_ERREXIT_RC"; false; echo ran-on-after'
    )
    sh = shutil.which("sh")
    if sh is None:
        pytest.fail("the host has no sh")
    run = subprocess.run(
        [sh, "-c", script, "sh", str(funcs)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.stdout == "rc=1\n"
    assert run.returncode == 1
