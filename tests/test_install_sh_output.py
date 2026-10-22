"""install.sh shows probcli's and fuzz's own output as text, never as control.

When probcli fails or reports the wrong version, or fuzz will not run,
install.sh prints what the tool said so the reader can see why. That output
comes from a binary the installer just downloaded or built, or one already
on PATH; an escape sequence in it must not reach the terminal verbatim,
where it could clear the screen or retitle the window. Both tools print
ASCII, so only tab and newline survive among the rest: C0 controls, DEL,
8-bit C1 controls (0x9B, CSI on some terminals), and every byte of a UTF-8
sequence (C2 9B encodes CSI too) are dropped. Checked at all five places
such output is printed: install_probcli's "would not run" and version
mismatch reports, the final report on the probcli PATH resolves to,
install_fuzz's probe of the fuzz it just built, and the final report on the
fuzz PATH resolves to.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Final

from tests.install_probcli_runner import SYSTEM, VERSION, Scenario
from tests.install_sh_runner import WholeInstall
from tests.prob_archive import ProbArchive

# ESC [ 2 J clears the screen; ESC ] 0 ; ... BEL sets the window title; DEL
# is the one control character outside 0-31; \233 is CSI as an 8-bit C1
# control, \302\233 the same CSI encoded as UTF-8; \303\251 is a plain
# UTF-8 letter, which goes too.
_HOSTILE: Final[str] = (
    r"printf 'probcli \033[2Jsays\033]0;owned\007 a\tb\177"
    r" \233[1mc1 \302\233[1mutf8 caf\303\251\n'"
)
# What is left once every byte but printable ASCII, tab and newline is gone.
_SHOWN: Final[str] = "probcli [2Jsays]0;owned a\tb [1mc1 [1mutf8 caf"
# How each hostile byte would read back if it leaked: raw (a lone
# surrogate, as surrogateescape decodes an invalid byte) or as UTF-8.
_LEAKS: Final[tuple[str, ...]] = (
    "\x1b",
    "\x07",
    "\x7f",
    "\x9b",
    "é",
    "\udc9b",
    "\udcc2",
    "\udcc3",
    "\udca9",
)


def _no_control(text: str) -> bool:
    return not any(c in text for c in _LEAKS)


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


def test_stripping_works_on_bytes_under_a_utf8_locale(tmp_path: Path) -> None:
    # \377 is never valid UTF-8. Under a UTF-8 locale BSD tr stops at it and
    # drops the rest; printable's own LC_ALL=C keeps it working on bytes.
    # GNU and busybox tr work on bytes in any locale, so this discriminates
    # on macOS (BSD tr) only.
    archive = ProbArchive.running(SYSTEM, r"printf 'before \377after\n' >&2; exit 1")
    scenario = replace(Scenario.pinned(archive), env=(("LC_ALL", "en_US.UTF-8"),))
    run = scenario.run(tmp_path)

    err = run.result.stderr
    assert run.result.returncode != 0
    assert "is installed but would not run:\nbefore after\n" in err, repr(err)
    assert "\udcff" not in err


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


def test_final_report_on_a_fuzz_on_path_strips_control_characters(
    tmp_path: Path,
) -> None:
    run = WholeInstall(str(tmp_path / "home"), fuzz=f"{_HOSTILE}; exit 1").run(tmp_path)

    err = run.result.stderr
    fuzz = tmp_path / "home" / ".local" / "bin" / "fuzz"
    assert f"fuzz resolves to {fuzz}, but it would not run:\n" in err, err
    assert f"  !   {_SHOWN}\n" in err, err
    assert _no_control(err), repr(err)


def test_probe_of_a_just_built_fuzz_strips_control_characters(
    tmp_path: Path,
) -> None:
    # --fuzz-only with the build tools stubbed: install_fuzz clones, makes
    # and installs (nothing), then probes the fuzz now at ~/.local/bin.
    home = tmp_path / "home"
    install = WholeInstall(
        str(home), args=("--fuzz-only",), fuzz=f"{_HOSTILE}; exit 1", build=True
    )
    run = install.run(tmp_path)

    err = run.result.stderr
    fuzz = home / ".local" / "bin" / "fuzz"
    assert run.result.returncode == 1
    assert run.calls("make") == [[], ["install"]], "the build never ran"
    assert f"  ! {fuzz} is installed but would not run:\n    {_SHOWN}\n" in err, err
    assert _no_control(err), repr(err)
