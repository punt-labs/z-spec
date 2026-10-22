"""install.sh's ProB download: bounded retries, HTTPS only, SHA-256 pinned.

The ProB archive host is a single university server that has dropped
connections and gone fully unreachable. ``install_probcli`` therefore runs
curl with bounded retries -- a single dropped connection recovers, a
sustained outage exits nonzero within minutes -- checks the pin's format
before any download, and verifies the archive against a per-OS SHA-256 pin
before reading anything inside it.

These tests run the shipped ``install_probcli`` function itself, not a copy,
through ``install_probcli_runner.Scenario``: offline, on a per-run PATH,
with curl stubbed and tar/unzip logged, so each test can say both what the
installer printed and which tools it never called.
"""

from __future__ import annotations

import io
import re
import tarfile
import zipfile
from dataclasses import replace
from pathlib import Path
from typing import Final

import pytest

from tests.install_probcli_runner import (
    GOOD,
    HOST_HASHERS,
    HOST_URL,
    SYSTEM,
    VERSION,
    Scenario,
)
from tests.install_sh_source import CurlFlags, Damage, InstallSh, ProbArchive

# Fixed flag -> value pairs every ProB fetch must carry (None: no value).
EXPECTED_FLAGS: Final[dict[str, str | None]] = {
    "-fL": None,
    "--proto": "=https",
    "--proto-redir": "=https",
    "--connect-timeout": "20",
    "--retry": "5",
    "--retry-connrefused": None,
    "--retry-max-time": "300",
    "--speed-limit": "1024",
    "--speed-time": "60",
}


def test_slice_ends_inside_the_installer() -> None:
    source = InstallSh().install_probcli_source()
    assert source.startswith("PROB_VERSION=")
    assert source.rstrip().endswith(")")


@pytest.mark.parametrize("curl_mode", ["modern", "old"])
def test_fetch_carries_exactly_the_https_only_bounded_retry_flags(
    tmp_path: Path, curl_mode: str
) -> None:
    # Exactly: a flag added to the real call (--insecure, -k) fails this.
    scenario = replace(Scenario.pinned(), curl_mode=curl_mode, fetch="refuse")
    expected = dict(EXPECTED_FLAGS)
    if curl_mode == "modern":
        expected["--retry-all-errors"] = None
    assert scenario.run(tmp_path).fetch_flags() == expected


def test_install_sh_flag_list_is_exactly_the_expected_pairs() -> None:
    assert InstallSh().fetch_flags().as_dict() == EXPECTED_FLAGS


def test_curl_flags_tell_swapped_values_apart() -> None:
    shipped = CurlFlags.parse(["--connect-timeout", "20", "--retry", "5"])
    swapped = CurlFlags.parse(["--connect-timeout", "5", "--retry", "20"])
    assert sorted(shipped.tokens()) == sorted(swapped.tokens())
    assert shipped.as_dict() != swapped.as_dict()


def test_curl_flags_reject_a_repeated_flag() -> None:
    with pytest.raises(ValueError, match="repeats a flag"):
        CurlFlags.parse(["--retry", "5", "--retry", "6"])


def test_modern_curl_also_retries_all_errors(tmp_path: Path) -> None:
    run = replace(Scenario.pinned(), fetch="refuse").run(tmp_path)
    assert "--retry-all-errors" in run.fetch()
    assert "predates --retry-all-errors" not in run.result.stderr


def test_old_curl_downloads_without_the_unknown_option_and_warns(
    tmp_path: Path,
) -> None:
    # A pre-7.71 curl rejects --retry-all-errors outright, so a probe that
    # does not actually pass the option would hand it to the fetch and turn
    # every install on such a system into "option is unknown".
    run = replace(Scenario.pinned(), curl_mode="old").run(tmp_path)

    assert "--retry-all-errors" not in run.fetch()
    assert "curl 7.68.0" in run.result.stderr
    assert "predates --retry-all-errors" in run.result.stderr
    assert run.result.returncode == 0, run.result.stderr


def test_sustained_failure_fails_loudly(tmp_path: Path) -> None:
    run = replace(Scenario.pinned(), fetch="refuse").run(tmp_path)

    assert run.result.returncode != 0
    assert f"download failed: {HOST_URL}" in run.result.stderr
    assert "Failed to connect" in run.result.stderr
    assert "could not read or hash" not in run.result.stderr


def test_interrupted_download_leaves_no_partial_archive(tmp_path: Path) -> None:
    run = replace(Scenario.pinned(), fetch="partial").run(tmp_path)

    assert run.result.returncode != 0
    assert f"download failed: {HOST_URL}" in run.result.stderr
    assert not run.archive_left(), "a partial download was left on disk"
    assert run.archive_reads() == []


def test_matching_pin_installs_and_runs_probcli(tmp_path: Path) -> None:
    run = Scenario.pinned().run(tmp_path)

    assert run.result.returncode == 0, run.result.stderr
    assert re.search(
        rf"✓ probcli \S+/ProB/probcli \({re.escape(VERSION)}\)$",
        run.result.stdout,
        re.M,
    ), run.result.stdout
    assert run.installed()
    assert not run.archive_left(), "a verified archive is removed after install"


@pytest.mark.parametrize("hasher", HOST_HASHERS)
def test_home_with_a_backslash_still_verifies(tmp_path: Path, hasher: str) -> None:
    # Given a file NAME with a backslash, sha256sum and shasum escape it and
    # prefix the hash with "\"; hashing stdin keeps the hash clean.
    run = replace(Scenario.pinned(), hashers=(hasher,), home="a\\b/home").run(tmp_path)

    assert "\\" in str(run.home)
    assert run.result.returncode == 0, run.result.stderr
    assert run.installed()


def test_mismatched_pin_fails_before_the_archive_is_read(tmp_path: Path) -> None:
    wrong = "0" * 64
    run = Scenario(pin=wrong).run(tmp_path)

    err = run.result.stderr
    assert run.result.returncode != 0
    assert "SHA-256 mismatch" in err
    assert f"expected: {wrong}" in err
    assert f"actual:   {GOOD.sha256()}" in err
    assert GOOD.name in err
    assert HOST_URL in err
    assert run.archive_reads() == [], "a mismatched archive was listed or extracted"
    assert not run.installed()
    assert not run.archive_left(), "the unverified archive was left on disk"


@pytest.mark.parametrize(
    "pin",
    [
        "PLACEHOLDER-unverified",
        "",
        "A" * 64,
        "0" * 63,
        "0" * 65,
        "g" * 64,
        "0" * 64 + "\n" + "0" * 64,
    ],
    ids=["placeholder", "empty", "uppercase", "short", "long", "non-hex", "2-lines"],
)
def test_non_hash_pin_fails_before_any_download(tmp_path: Path, pin: str) -> None:
    # A placeholder, an empty value, uppercase, or a wrong length must never
    # be read as "skip verification" -- and can never verify anything, so it
    # fails before a single request reaches the ProB host.
    run = Scenario(pin=pin).run(tmp_path)

    err = run.result.stderr
    assert run.result.returncode != 0
    assert f"no verified SHA-256 pin for {GOOD.name}" in err
    assert f"pin is not 64 lowercase hex digits (value: {pin})" in err
    assert "SHA-256 mismatch" not in err
    assert run.calls("curl") == [], "a non-hash pin still reached curl"
    assert run.archive_reads() == []
    assert not run.installed()
    assert not run.archive_left()


def test_shipped_pins_fail_closed(tmp_path: Path) -> None:
    # Each shipped value is a real hash or a marked placeholder; for this
    # OS's, whatever it is -- a placeholder today ("no verified pin"), a real
    # hash once one lands ("mismatch" against this fixture) -- the served
    # archive is never read, installed, or kept.
    for name, value in InstallSh().pins().items():
        assert re.fullmatch(r"[0-9a-f]{64}", value) or value.startswith(
            "PLACEHOLDER-"
        ), f"install.sh {name} is neither a SHA-256 nor a marked placeholder: {value!r}"
    run = Scenario().run(tmp_path)

    err = run.result.stderr
    assert run.result.returncode != 0
    assert "no verified SHA-256 pin" in err or "SHA-256 mismatch" in err, err
    assert run.archive_reads() == []
    assert not run.installed()
    assert not run.archive_left()


@pytest.mark.parametrize("member", ["../escaped", "ProB/../../escaped", "/escaped"])
def test_pinned_archive_with_an_escaping_member_is_never_extracted(
    tmp_path: Path, member: str
) -> None:
    # The pin only proves the archive is the one the publisher shipped; the
    # slip guard is what stops a hostile publisher's ../ or absolute member.
    run = Scenario.pinned(ProbArchive.with_probcli(SYSTEM, VERSION, member)).run(
        tmp_path
    )

    assert run.result.returncode != 0
    assert "contains an absolute or ../ path -- refusing to extract" in (
        run.result.stderr
    )
    assert run.extractions() == [], f"an archive with {member!r} was extracted"
    assert not run.escaped()
    assert not run.installed()


def test_shasum_fallback_installs_when_sha256sum_is_absent(tmp_path: Path) -> None:
    run = replace(Scenario.pinned(), hashers=("shasum",)).run(tmp_path)

    assert run.result.returncode == 0, run.result.stderr
    assert run.installed()


def test_no_hash_tool_fails_before_any_download(tmp_path: Path) -> None:
    run = replace(Scenario.pinned(), hashers=()).run(tmp_path)

    assert run.result.returncode != 0
    assert "neither sha256sum nor shasum found" in run.result.stderr
    assert run.fetches() == [], "downloaded with nothing to verify it"
    assert not run.installed()


def test_failing_hash_tool_is_not_reported_as_a_mismatch(tmp_path: Path) -> None:
    run = replace(Scenario.pinned(), broken_hashers=True).run(tmp_path)

    err = run.result.stderr
    assert run.result.returncode != 0
    assert "could not read or hash" in err
    assert "SHA-256 mismatch" not in err
    assert run.archive_reads() == []
    assert not run.installed()
    assert not run.archive_left()


def test_probcli_reporting_another_version_fails(tmp_path: Path) -> None:
    other = f"{VERSION}0"  # 1.15.10 must not pass as 1.15.1
    run = Scenario.pinned(ProbArchive.with_probcli(SYSTEM, other)).run(tmp_path)

    assert run.result.returncode != 0
    assert f"expected probcli {VERSION}, got: {other}" in run.result.stderr
    assert "✓ probcli" not in run.result.stdout


def test_probcli_printing_no_version_is_unreadable_and_shown(tmp_path: Path) -> None:
    # The archive's probcli prints "ProB command line, version " and no x.y.z.
    run = Scenario.pinned(ProbArchive.with_probcli(SYSTEM, "")).run(tmp_path)

    err = run.result.stderr
    assert run.result.returncode != 0
    assert f"expected probcli {VERSION}, got: unreadable\n" in err
    assert "/probcli -version printed:\n      ProB command line, version" in err


@pytest.mark.parametrize("damage", ["not-an-archive", "bad-checksum"])
def test_pinned_archive_that_does_not_read_is_never_extracted(
    tmp_path: Path, damage: Damage
) -> None:
    # Pinned to its own hash, so only the archive integrity check stands
    # between it and the extractor.
    run = Scenario.pinned(GOOD.damaged(damage)).run(tmp_path)

    kind = "zip archive" if SYSTEM == "Darwin" else "gzip tarball"
    assert run.result.returncode != 0
    assert HOST_URL in run.result.stderr
    assert f"did not return a {kind} (got: " in run.result.stderr
    assert run.extractions() == []
    assert not run.installed()


def test_pinned_archive_without_probcli_fails(tmp_path: Path) -> None:
    run = Scenario.pinned(ProbArchive.without_probcli(SYSTEM)).run(tmp_path)

    err = run.result.stderr
    assert run.result.returncode != 0
    archive = run.home / "Applications" / GOOD.name
    assert f"extracted {archive} but there is no probcli" in err
    assert "✓ probcli" not in run.result.stdout
    assert not run.installed()


@pytest.mark.parametrize("home", ["home", ""], ids=["relative", "empty"])
def test_non_absolute_home_fails_before_anything_else(
    tmp_path: Path, home: str
) -> None:
    run = replace(Scenario.pinned(), home=home, absolute_home=False).run(tmp_path)

    assert run.result.returncode != 0
    assert f"HOME is not an absolute path (HOME='{home}')" in run.result.stderr
    assert run.calls("curl") == [], "a relative HOME still reached the host"
    assert not (tmp_path / home / "Applications").exists()


# The fixtures must not depend on the clock: a pin hashed from one build has
# to verify the next. The timestamps are checked where they live, in the
# headers, since two builds in the same second would agree by accident.
def test_tar_fixture_carries_no_timestamp() -> None:
    data = ProbArchive.with_probcli("Linux", VERSION).data()
    assert data[:2] == b"\x1f\x8b"
    assert data[4:8] == b"\0\0\0\0", "gzip MTIME must be zero for a stable hash"
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
        assert [m.mtime for m in tf.getmembers()] == [0]


def test_zip_fixture_carries_a_fixed_timestamp() -> None:
    data = ProbArchive.with_probcli("Darwin", VERSION, "ProB/x").data()
    # Local file header: signature, then mod time (bytes 10-11) and mod
    # date (12-13); 1980-01-01 00:00:00 is time 0, date 0x0021.
    assert data[:4] == b"PK\x03\x04"
    assert data[10:14] == b"\x00\x00\x21\x00"
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        assert {i.date_time for i in zf.infolist()} == {(1980, 1, 1, 0, 0, 0)}
