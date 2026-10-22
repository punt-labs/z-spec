"""install.sh's handling of a verified ProB archive: read, guard, extract, run.

Every archive here is pinned to its own hash, so the SHA-256 check passes
and only what follows it -- the integrity check, the slip guard, the layout
check, and the exact-version check -- stands between the archive and an
installed probcli.

Run through ``install_probcli_runner.Scenario``, as the fetch tests are.
The tests whose outcome depends on the archive format run both of
install_probcli's branches, the macOS zip and the Linux tar.gz, on every
host: the scenario's ``uname`` reports the archive's OS.
"""

from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path

import pytest

from tests.install_probcli_runner import (
    HOST_URL,
    SYSTEM,
    SYSTEMS,
    VERSION,
    Scenario,
)
from tests.prob_archive import Damage, ProbArchive


@pytest.mark.parametrize("system", SYSTEMS)
@pytest.mark.parametrize("member", ["../escaped", "ProB/../../escaped", "/escaped"])
def test_pinned_archive_with_an_escaping_member_is_never_extracted(
    tmp_path: Path, member: str, system: str
) -> None:
    # The pin only proves the archive is the one the publisher shipped; the
    # slip guard is what stops a hostile publisher's ../ or absolute member.
    run = Scenario.pinned(ProbArchive.with_probcli(system, VERSION, member)).run(
        tmp_path
    )

    assert run.result.returncode != 0
    assert "contains an absolute or ../ path -- refusing to extract" in (
        run.result.stderr
    )
    assert run.extractions() == [], f"an archive with {member!r} was extracted"
    assert not run.escaped()
    assert not run.installed()
    assert not run.archive_left(), "a refused archive was left on disk"


def test_probcli_reporting_another_version_fails(tmp_path: Path) -> None:
    other = f"{VERSION}0"  # 1.15.10 must not pass as 1.15.1
    run = Scenario.pinned(ProbArchive.with_probcli(SYSTEM, other)).run(tmp_path)

    assert run.result.returncode != 0
    assert f"expected probcli {VERSION}, got: {other}" in run.result.stderr
    assert "✓ probcli" not in run.result.stdout
    assert not run.archive_left(), "the archive was left after a version mismatch"


def test_probcli_that_will_not_run_fails_and_shows_why(tmp_path: Path) -> None:
    body = "echo 'error while loading shared libraries: libtcl8.6.so' >&2; exit 127"
    run = Scenario.pinned(ProbArchive.running(SYSTEM, body)).run(tmp_path)

    err = run.result.stderr
    assert run.result.returncode != 0
    assert "/ProB/probcli is installed but would not run:\n" in err
    assert "libtcl8.6.so" in err
    assert not run.archive_left(), "the archive was left after probcli failed"


def test_probcli_printing_no_version_is_unreadable_and_shown(tmp_path: Path) -> None:
    # The archive's probcli prints "ProB command line, version " and no x.y.z.
    run = Scenario.pinned(ProbArchive.with_probcli(SYSTEM, "")).run(tmp_path)

    err = run.result.stderr
    assert run.result.returncode != 0
    assert f"expected probcli {VERSION}, got: unreadable\n" in err
    assert "/probcli -version printed:\n      ProB command line, version" in err


@pytest.mark.parametrize("system", SYSTEMS)
@pytest.mark.parametrize("damage", ["not-an-archive", "corrupt"])
def test_pinned_archive_that_does_not_read_is_never_extracted(
    tmp_path: Path, damage: Damage, system: str
) -> None:
    # Pinned to its own hash, so only the archive integrity check stands
    # between it and the extractor.
    served = ProbArchive.with_probcli(system, VERSION).damaged(damage)
    run = Scenario.pinned(served).run(tmp_path)

    kind = "zip archive" if system == "Darwin" else "gzip tarball"
    url = f"{HOST_URL}downloads/prob/tcltk/releases/{VERSION}/{served.name}"
    assert run.result.returncode != 0
    # One line: the URL that served it, and what `file` says it is instead.
    assert re.search(
        rf"^  ! {re.escape(url)} did not return a {kind} \(got: \S.*\)$",
        run.result.stderr,
        re.M,
    ), run.result.stderr
    assert run.extractions() == []
    assert not run.installed()
    assert not run.archive_left(), "an archive that does not read was left"


@pytest.mark.parametrize("system", SYSTEMS)
def test_pinned_archive_without_probcli_fails(tmp_path: Path, system: str) -> None:
    served = ProbArchive.without_probcli(system)
    run = Scenario.pinned(served).run(tmp_path)

    err = run.result.stderr
    assert run.result.returncode != 0
    archive = run.home / "Applications" / served.name
    assert f"extracted {archive} but there is no probcli" in err
    assert "✓ probcli" not in run.result.stdout
    assert not run.installed()
    assert not run.archive_left(), "an archive with no probcli was left"


@pytest.mark.parametrize("system", SYSTEMS)
def test_failed_extraction_names_the_archive_and_its_destination(
    tmp_path: Path, system: str
) -> None:
    # The archive verifies and lists cleanly; only the extractor fails. The
    # destination already holds a ProB install, which must survive.
    earlier = tmp_path / "home" / "Applications" / "ProB" / "installed-before"
    earlier.parent.mkdir(parents=True)
    earlier.write_text("an earlier ProB install\n", encoding="utf-8")
    served = ProbArchive.with_probcli(system, VERSION)
    run = replace(Scenario.pinned(served), extraction_fails=True).run(tmp_path)

    err = run.result.stderr
    archive = run.home / "Applications" / served.name
    assert run.result.returncode != 0
    assert len(run.extractions()) == 1, "the verified archive never reached it"
    assert "simulated extraction failure" in err, "the extractor never failed"
    assert f"could not extract {archive} into {run.home / 'Applications'}\n" in err
    assert "no probcli at" not in err, "ran on past the failed extraction"
    assert not run.installed()
    assert not run.archive_left(), "the archive was left after a failed extraction"
    assert earlier.exists(), "a failed run removed an earlier install under DEST"


def test_zip_whose_listing_fails_is_never_extracted(tmp_path: Path) -> None:
    # The zip passes its integrity test (unzip -tq runs the real tool); only
    # unzip -Z1 fails. Ignoring that would leave the slip guard checking an
    # empty listing and let unzip extract members it never saw.
    served = ProbArchive.with_probcli("Darwin", VERSION)
    run = replace(Scenario.pinned(served), listing_fails=True).run(tmp_path)

    err = run.result.stderr
    archive = run.home / "Applications" / served.name
    assert run.result.returncode != 0
    assert [c[0] for c in run.calls("unzip")] == ["-tq", "-Z1"]
    assert "unzip: simulated listing failure" in err
    assert f"  ! could not list {archive}\n" in err, err
    assert run.extractions() == [], "an archive whose listing failed was extracted"
    assert not run.installed()
    assert not run.archive_left(), "an archive whose listing failed was left"
