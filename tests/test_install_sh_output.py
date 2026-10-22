"""install.sh shows probcli's own output as text, never as terminal control.

When probcli fails or reports the wrong version, install.sh prints what it
said so the reader can see why. That output comes from a binary the
installer just downloaded, or one already on PATH; an escape sequence in it
must not reach the terminal verbatim, where it could clear the screen or
retitle the window. Tab and newline are text and survive. Checked at all
three places it is printed: install_probcli's "would not run" and version
mismatch reports, and the final report on the probcli PATH resolves to.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from tests.install_probcli_runner import SYSTEM, VERSION, Scenario
from tests.install_sh_runner import WholeInstall
from tests.prob_archive import ProbArchive

# ESC [ 2 J clears the screen; ESC ] 0 ; ... BEL sets the window title.
_HOSTILE: Final[str] = r"printf 'probcli \033[2Jsays\033]0;owned\007 a\tb\n'"
# What is left once every control character but tab and newline is gone.
_SHOWN: Final[str] = "probcli [2Jsays]0;owned a\tb"
_CONTROL: Final[tuple[str, ...]] = ("\x1b", "\x07")


def _no_control(text: str) -> bool:
    return not any(c in text for c in _CONTROL)


def test_version_mismatch_report_strips_control_characters(tmp_path: Path) -> None:
    archive = ProbArchive.running(SYSTEM, _HOSTILE)
    run = Scenario.pinned(archive).run(tmp_path)

    err = run.result.stderr
    assert run.result.returncode != 0
    assert f"expected probcli {VERSION}, got: unreadable\n" in err
    assert f"\n      {_SHOWN}\n" in err, err
    assert _no_control(err), repr(err)


def test_would_not_run_report_strips_control_characters(tmp_path: Path) -> None:
    archive = ProbArchive.running(SYSTEM, f"{_HOSTILE} >&2; exit 1")
    run = Scenario.pinned(archive).run(tmp_path)

    err = run.result.stderr
    assert run.result.returncode != 0
    assert f"is installed but would not run:\n{_SHOWN}\n" in err, err
    assert _no_control(err), repr(err)


def test_final_report_on_a_probcli_on_path_strips_control_characters(
    tmp_path: Path,
) -> None:
    run = WholeInstall(str(tmp_path / "home"), probcli=f"{_HOSTILE}; exit 1").run(
        tmp_path
    )

    err = run.result.stderr
    assert run.calls("path-probcli"), "the probcli on PATH never ran"
    assert "probcli resolves to " in err and "but it would not run:" in err, err
    assert f"  !   {_SHOWN}\n" in err, err
    assert _no_control(err), repr(err)
