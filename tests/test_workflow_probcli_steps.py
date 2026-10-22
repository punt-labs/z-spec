"""The specs job's ProB steps, run offline: what they do, not where they sit.

Each test runs a shipped ``run:`` block through ``workflow_step_runner``:
under ``bash -e`` with a stub-first PATH, so a tampered, unpinned, missing,
corrupt, or hostile archive can be served or cached and every tar/unzip/curl
call observed. Three steps are covered: the pin selection, the install, and
the verify.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Final

import pytest

from tests.install_sh_source import Damage, ProbArchive
from tests.workflow_source import Workflow
from tests.workflow_step_runner import CACHE_KEY, InstallStep, StepHarness

_HOST: Final[str] = "stups.hhu-hosting.de"
_SYSTEMS: Final[list[str]] = ["Linux", "Darwin"]
_PIN_VARS: Final[dict[str, str]] = {
    "Linux": "PROB_SHA256_LINUX",
    "Darwin": "PROB_SHA256_MACOS",
}
_WF: Final[Workflow] = Workflow()
_VERSION: Final[str] = _WF.job_env("specs", "PROB_VERSION")
_BAD_PINS: Final[dict[str, str]] = {
    "placeholder": "PLACEHOLDER-unverified-awaiting-download-from-prob-host",
    "empty": "",
    "uppercase": "A" * 64,
    "short": "0" * 63,
    "long": "0" * 65,
    "non-hex": "g" * 64,
    "two-lines": "0" * 64 + "\nnot-a-hash",
}
# The malformed pins the select step names as such: an empty one fails
# earlier (${VAR:?}), and a two-line one gets its own message.
_MALFORMED: Final[dict[str, str]] = {
    k: v for k, v in _BAD_PINS.items() if k not in ("empty", "two-lines")
}


def _url(archive: ProbArchive) -> str:
    return f"https://{_HOST}/downloads/prob/tcltk/releases/{_VERSION}/{archive.name}"


def _good(system: str, *extra: str) -> ProbArchive:
    return ProbArchive.with_probcli(system, _VERSION, *extra)


# --- Behaviour: the select step ---------------------------------------------


@pytest.mark.parametrize(
    ("runner_os", "system"), [("Linux", "Linux"), ("macOS", "Darwin")]
)
def test_select_outputs_this_os_archive_and_pin(
    tmp_path: Path, runner_os: str, system: str
) -> None:
    pins = {"PROB_SHA256_LINUX": "1" * 64, "PROB_SHA256_MACOS": "2" * 64}
    run = StepHarness.select(runner_os, pins).run(tmp_path)
    assert run.result.returncode == 0, run.result.stderr
    archive, pin = _good(system).name, pins[_PIN_VARS[system]]
    assert run.file("github_output") == f"archive={archive}\nsha256={pin}\n"


@pytest.mark.parametrize(
    ("runner_os", "pin", "message"),
    [
        ("Windows", "1" * 64, "no ProB archive for runner OS 'Windows'"),
        ("Linux", "", "PROB_SHA256_LINUX is empty"),
        ("macOS", "", "PROB_SHA256_MACOS is empty"),
        ("Linux", "1" * 64 + "\nsha256=" + "2" * 64, "spans more than one line"),
    ],
)
def test_select_refuses_and_writes_no_output(
    tmp_path: Path, runner_os: str, pin: str, message: str
) -> None:
    pins = dict.fromkeys(_PIN_VARS.values(), pin)
    run = StepHarness.select(runner_os, pins).run(tmp_path)
    assert run.result.returncode != 0
    assert message in run.result.stderr
    assert "no verified SHA-256 pin" not in run.result.stderr, "ran on past its cause"
    assert run.file("github_output") == ""


@pytest.mark.parametrize(
    ("runner_os", "system"), [("Linux", "Linux"), ("macOS", "Darwin")]
)
@pytest.mark.parametrize("pin", _MALFORMED.values(), ids=_MALFORMED.keys())
def test_select_refuses_a_malformed_pin_before_the_cache_key(
    tmp_path: Path, runner_os: str, system: str, pin: str
) -> None:
    # The cache key is built from this step's output; a pin that can never
    # verify an archive must not reach it.
    pins = dict.fromkeys(_PIN_VARS.values(), pin)
    run = StepHarness.select(runner_os, pins).run(tmp_path)
    err = run.result.stderr
    assert run.result.returncode != 0
    assert f"FATAL: no verified SHA-256 pin for {_good(system).name}" in err
    assert f"pin is not 64 lowercase hex digits (value: {pin})" in err
    assert run.file("github_output") == ""


# --- Behaviour: the install step ---------------------------------------------


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
    shipped = _WF.job_env("specs", _PIN_VARS[system])
    run = InstallStep(_good(system), shipped, cache_hit=True, cached=True).run(tmp_path)
    err = run.result.stderr
    assert run.result.returncode != 0
    assert "no verified SHA-256 pin" in err or "SHA-256 mismatch" in err, err
    assert run.archive_reads() == []
    assert "PROBCLI=" not in run.file("github_env")


@pytest.mark.parametrize("system", _SYSTEMS)
@pytest.mark.parametrize("pin", _BAD_PINS.values(), ids=_BAD_PINS.keys())
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
@pytest.mark.parametrize("damage", ["not-an-archive", "bad-checksum"])
def test_pinned_archive_that_does_not_read_is_named_as_such(
    tmp_path: Path, system: str, cache_hit: bool, damage: Damage
) -> None:
    # Pinned to its own hash, so only the archive integrity check stands
    # between it and the extractor: an error page, a zip whose listing reads
    # but whose CRC test fails, a tarball whose gzip CRC fails.
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
    assert f"FATAL: no probcli in the ProB {_VERSION} archive from cache key " in err
    assert "ProB/README" in err, "the extracted tree is not listed"
    assert "PROBCLI=" not in run.file("github_env")


@pytest.mark.parametrize("system", _SYSTEMS)
def test_extraction_failure_names_the_verified_archive(
    tmp_path: Path, system: str
) -> None:
    good = _good(system)
    step = InstallStep(good, good.sha256(), cache_hit=True, cached=True)
    run = replace(step, writable_dest=False).run(tmp_path)
    err = run.result.stderr
    assert run.result.returncode != 0
    assert f"FATAL: could not extract {good.name} (from cache key {CACHE_KEY})" in err
    assert "its SHA-256 matched the pin" in err
    assert "no probcli in the ProB" not in err, "ran on past the failed extraction"
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


# --- Behaviour: the verify step ----------------------------------------------


@pytest.mark.parametrize(
    "body",
    [
        f"echo 'ProB command line, version {_VERSION}'",
        f"echo 'ProB command line, version {_VERSION}' >&2",
        f"echo 'ProB {_VERSION}'; echo 'built with Tcl 8.6.13, SICStus 4.9.0'",
    ],
    ids=["stdout", "stderr-only", "first-version-wins"],
)
def test_verify_accepts_the_pinned_version(tmp_path: Path, body: str) -> None:
    result = StepHarness.verify(body).run(tmp_path).result
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    ("body", "got"),
    [
        (f"echo 'ProB {_VERSION}0'", f"{_VERSION}0"),
        ("echo 'ProB, no version'", "unreadable"),
    ],
)
def test_verify_rejects_any_other_version(tmp_path: Path, body: str, got: str) -> None:
    result = StepHarness.verify(body).run(tmp_path).result
    assert result.returncode != 0
    assert f"FATAL: expected probcli {_VERSION}, got: {got}" in result.stderr


def test_verify_shows_why_probcli_would_not_run(tmp_path: Path) -> None:
    body = "echo 'error while loading shared libraries: libtcl8.6.so' >&2; exit 127"
    result = StepHarness.verify(body).run(tmp_path).result
    assert result.returncode != 0
    assert "-version failed; its output:" in result.stderr
    assert "libtcl8.6.so" in result.stderr


def test_verify_names_a_missing_fuzz(tmp_path: Path) -> None:
    # PATH is the stub directory alone: a host fuzz cannot satisfy the step.
    result = StepHarness.verify(f"echo {_VERSION}", fuzz=False).run(tmp_path).result
    assert result.returncode != 0
    assert "FATAL: fuzz is not on PATH" in result.stderr
