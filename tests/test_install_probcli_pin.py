"""install.sh's ProB pin: a per-OS SHA-256, checked before anything is read.

``install_probcli`` checks the pin's format before any download and verifies
the archive against it before listing or extracting anything inside. A pin
that is not 64 lowercase hex digits never means "skip verification", and a
hash tool that fails is never reported as a mismatch.

Run through ``install_probcli_runner.Scenario``, as the fetch tests are.
"""

from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path

import pytest

from tests.install_probcli_runner import GOOD, HOST_URL, Scenario
from tests.install_sh_source import InstallSh


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


def test_shipped_pins_are_real_hashes_that_reject_the_fixture(tmp_path: Path) -> None:
    # Every shipped value is a real SHA-256 of a real ProB archive, so the
    # fixture this OS is served can only fail as a mismatch -- never as "no
    # verified pin" -- and is never read, installed, or kept.
    for name, value in InstallSh().pins().items():
        assert re.fullmatch(r"[0-9a-f]{64}", value), (
            f"install.sh {name} is not a SHA-256: {value!r}"
        )
    run = Scenario().run(tmp_path)

    err = run.result.stderr
    assert run.result.returncode != 0
    assert "SHA-256 mismatch" in err, err
    assert "no verified SHA-256 pin" not in err, err
    assert run.archive_reads() == []
    assert not run.installed()
    assert not run.archive_left()


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
