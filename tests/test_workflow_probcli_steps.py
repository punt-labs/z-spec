"""The specs job's install step, run offline: what it does, not where it sits.

Each test runs the shipped "Install probcli" ``run:`` block through
``workflow_step_runner``: under ``bash -e`` with a stub-first PATH, so a
tampered, unpinned, missing, corrupt, or hostile archive can be served or
cached and every tar/unzip/curl call observed. The pin selection and the
verify step have their own modules.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Final

import pytest

from tests.prob_archive import Damage, ProbArchive
from tests.workflow_source import Workflow
from tests.workflow_step_runner import (
    BAD_PINS,
    CACHE_KEY,
    PIN_VARS,
    PROB_VERSION,
    InstallStep,
)

_HOST: Final[str] = "stups.hhu-hosting.de"
_SYSTEMS: Final[list[str]] = ["Linux", "Darwin"]
_WF: Final[Workflow] = Workflow()


def _url(archive: ProbArchive) -> str:
    return (
        f"https://{_HOST}/downloads/prob/tcltk/releases/{PROB_VERSION}/{archive.name}"
    )


def _good(system: str, *extra: str) -> ProbArchive:
    return ProbArchive.with_probcli(system, PROB_VERSION, *extra)


@pytest.mark.parametrize("system", _SYSTEMS)
@pytest.mark.parametrize("cache_hit", [True, False], ids=["hit", "miss"])
def test_tampered_archive_fails_closed(
    tmp_path: Path, system: str, cache_hit: bool
) -> None:
    good = _good(system)
    tampered = _good(system, "ProB/x")
    step = InstallStep(tampered, good.sha256(), cache_hit=cache_hit, cached=cache_hit)
    run = step.run(tmp_path)
    err = run.result.stderr
    assert run.result.returncode != 0
    assert f"FATAL: SHA-256 mismatch for {good.name}" in err
    if cache_hit:
        assert f"gh cache delete '{CACHE_KEY}'" in err
        assert run.calls("curl") == [], "a cache hit contacted the host"
    else:
        assert f"download https://{_HOST}/" in err
    assert run.archive_reads() == [], "a tampered archive was read"
    assert "PROBCLI=" not in run.file("github_env")


@pytest.mark.parametrize("system", _SYSTEMS)
def test_shipped_pin_never_installs_the_fixture(tmp_path: Path, system: str) -> None:
    # A placeholder today ("no verified pin"), a real hash once one lands
    # ("mismatch" against this fixture): the fixture is never read.
    shipped = _WF.job_env("specs", PIN_VARS[system])
    run = InstallStep(_good(system), shipped, cache_hit=True, cached=True).run(tmp_path)
    err = run.result.stderr
    assert run.result.returncode != 0
    assert "no verified SHA-256 pin" in err or "SHA-256 mismatch" in err, err
    assert run.archive_reads() == []
    assert "PROBCLI=" not in run.file("github_env")


@pytest.mark.parametrize("system", _SYSTEMS)
@pytest.mark.parametrize("pin", BAD_PINS.values(), ids=BAD_PINS.keys())
def test_non_hash_pin_fails_before_any_download(
    tmp_path: Path, system: str, pin: str
) -> None:
    run = InstallStep(_good(system), pin).run(tmp_path)  # a cache miss
    err = run.result.stderr
    assert run.result.returncode != 0
    assert "FATAL: no verified SHA-256 pin" in err
    first_line = pin.split("\n")[0]
    assert f"pin is not 64 lowercase hex digits (value: {first_line}" in err
    assert "SHA-256 mismatch" not in err
    assert run.calls("curl") == [], "a malformed pin still reached the host"
    assert run.archive_reads() == []


def test_unknown_archive_name_fails(tmp_path: Path) -> None:
    # A well-formed pin, so only the archive-name check can stop the step.
    good = _good("Linux")
    run = InstallStep(good, good.sha256(), archive_name="").run(tmp_path)
    assert run.result.returncode != 0
    assert "unknown ProB archive name ''" in run.result.stderr
    assert run.calls("curl") == [], "an unknown archive name reached the host"


def test_cache_hit_with_no_archive_fails(tmp_path: Path) -> None:
    good = _good("Linux")
    run = InstallStep(good, good.sha256(), cache_hit=True).run(tmp_path)
    assert run.result.returncode != 0
    assert "FATAL: cache hit but" in run.result.stderr
    assert f"gh cache delete '{CACHE_KEY}'" in run.result.stderr
    assert run.calls("curl") == []


@pytest.mark.parametrize("system", _SYSTEMS)
@pytest.mark.parametrize("cache_hit", [True, False], ids=["hit", "miss"])
def test_matching_pin_installs_probcli(
    tmp_path: Path, system: str, cache_hit: bool
) -> None:
    run = InstallStep.pinned(_good(system), cache_hit=cache_hit).run(tmp_path)
    assert run.result.returncode == 0, run.result.stderr
    probcli = run.runner_temp / "ProB" / "ProB" / "probcli"
    assert f"PROBCLI={probcli}\nPROB_HOME={probcli.parent}\n" == run.file("github_env")
    assert len(run.calls("curl")) == (0 if cache_hit else 1)
    restored = f"archive restored from cache key {CACHE_KEY} -- no download"
    assert (restored in run.result.stdout) == cache_hit, run.result.stdout


def test_cache_miss_logs_the_url_it_fetches(tmp_path: Path) -> None:
    good = _good("Linux")
    run = InstallStep.pinned(good, cache_hit=False).run(tmp_path)
    url = _url(good)
    expected = f"cache miss (cache-hit='false', key {CACHE_KEY}) -- downloading {url}"
    assert expected in run.result.stdout
    assert run.calls("curl")[0][-1] == url


@pytest.mark.parametrize("system", _SYSTEMS)
@pytest.mark.parametrize("cache_hit", [True, False], ids=["hit", "miss"])
@pytest.mark.parametrize("damage", ["not-an-archive", "corrupt"])
def test_pinned_archive_that_does_not_read_is_named_as_such(
    tmp_path: Path, system: str, cache_hit: bool, damage: Damage
) -> None:
    # Pinned to its own hash, so only the archive integrity check stands
    # between it and the extractor: an error page, a zip whose listing reads
    # but whose CRC test fails, a tarball whose gzip stream ends early.
    served = _good(system).damaged(damage)
    run = InstallStep.pinned(served, cache_hit=cache_hit).run(tmp_path)
    err = run.result.stderr
    assert run.result.returncode != 0
    assert f"FATAL: {served.name} from " in err
    assert "is not a valid archive (file -b: " in err
    if cache_hit:
        assert f"cache key {CACHE_KEY}" in err
        assert f"gh cache delete '{CACHE_KEY}'" in err
    else:
        assert f"download {_url(served)}" in err
    assert run.extractions() == [], "an archive that does not read was extracted"
    assert "PROBCLI=" not in run.file("github_env")


@pytest.mark.parametrize("system", _SYSTEMS)
def test_pinned_archive_without_probcli_fails(tmp_path: Path, system: str) -> None:
    archive = ProbArchive.without_probcli(system)
    run = InstallStep.pinned(archive, cache_hit=True).run(tmp_path)
    err = run.result.stderr
    assert run.result.returncode != 0
    assert (
        f"FATAL: no probcli in the ProB {PROB_VERSION} archive from cache key " in err
    )
    assert "ProB/README" in err, "the extracted tree is not listed"
    assert "PROBCLI=" not in run.file("github_env")


@pytest.mark.parametrize("system", _SYSTEMS)
def test_extraction_failure_names_the_verified_archive(
    tmp_path: Path, system: str
) -> None:
    good = _good(system)
    step = InstallStep(good, good.sha256(), cache_hit=True, cached=True)
    run = replace(step, extraction_fails=True).run(tmp_path)
    err = run.result.stderr
    assert run.result.returncode != 0
    assert len(run.extractions()) == 1, "the verified archive never reached tar/unzip"
    assert "simulated extraction failure" in err, "the extractor never failed"
    assert f"FATAL: could not extract {good.name} (from cache key {CACHE_KEY})" in err
    assert "its SHA-256 matched the pin" in err
    assert "no probcli in the ProB" not in err, "ran on past the failed extraction"
    assert "PROBCLI=" not in run.file("github_env")


@pytest.mark.parametrize("cache_hit", [True, False], ids=["hit", "miss"])
def test_zip_whose_listing_fails_is_never_extracted(
    tmp_path: Path, cache_hit: bool
) -> None:
    # The zip passes unzip -tq (the real tool runs); only unzip -Z1 fails.
    # Ignoring that would leave the slip guard checking an empty listing.
    good = _good("Darwin")
    step = replace(InstallStep.pinned(good, cache_hit=cache_hit), listing_fails=True)
    run = step.run(tmp_path)
    err = run.result.stderr
    assert run.result.returncode != 0
    assert [c[0] for c in run.calls("unzip")] == ["-tq", "-Z1"]
    assert "unzip: simulated listing failure" in err
    assert f"FATAL: {good.name} from " in err
    assert "is not a valid archive (file -b: " in err
    assert run.extractions() == [], "an archive whose listing failed was extracted"
    assert "PROBCLI=" not in run.file("github_env")


@pytest.mark.parametrize("system", _SYSTEMS)
@pytest.mark.parametrize("member", ["../escaped", "ProB/../../escaped", "/escaped"])
def test_pinned_archive_with_an_escaping_member_is_refused(
    tmp_path: Path, system: str, member: str
) -> None:
    run = InstallStep.pinned(_good(system, member), cache_hit=True).run(tmp_path)
    assert run.result.returncode != 0
    assert "contains unsafe paths (absolute or ../)" in run.result.stderr
    assert run.extractions() == [], f"an archive with {member!r} was extracted"
    assert not (run.runner_temp / "escaped").exists()
    assert not (run.runner_temp / "ProB" / "escaped").exists()


def test_failing_hash_tool_is_not_a_mismatch(tmp_path: Path) -> None:
    good = _good("Linux")
    step = InstallStep(
        good, good.sha256(), cache_hit=True, cached=True, broken_shasum=True
    )
    err = step.run(tmp_path).result.stderr
    assert "FATAL: could not read or hash" in err
    assert "SHA-256 mismatch" not in err


def test_download_failure_names_the_url_and_stops(tmp_path: Path) -> None:
    good = _good("Linux")
    run = InstallStep(good, good.sha256(), fetch="refuse").run(tmp_path)
    assert run.result.returncode != 0
    assert f"FATAL: ProB download failed: https://{_HOST}/" in run.result.stderr
    assert "could not read or hash" not in run.result.stderr, "ran on past curl"
    assert run.archive_reads() == []
