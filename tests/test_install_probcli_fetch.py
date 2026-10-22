"""install.sh's ProB download: bounded retries, HTTPS only, nothing left behind.

The ProB archive host is a single university server that has dropped
connections and gone fully unreachable. ``install_probcli`` therefore runs
curl with bounded retries -- a single dropped connection recovers, a
sustained outage exits nonzero within minutes -- over HTTPS only.

These tests run the shipped ``install_probcli`` function itself, not a copy,
through ``install_probcli_runner.Scenario``: offline, on a per-run PATH,
with curl stubbed and tar/unzip logged, so each test can say both what the
installer printed and which tools it never called. The pin and the archive
checks have their own modules.
"""

from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path
from typing import Final

import pytest

from tests.install_probcli_runner import (
    HOST_HASHERS,
    HOST_URL,
    VERSION,
    Scenario,
)
from tests.install_sh_source import CurlFlags, InstallSh

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


@pytest.mark.parametrize("home", ["home", ""], ids=["relative", "empty"])
def test_non_absolute_home_fails_before_anything_else(
    tmp_path: Path, home: str
) -> None:
    run = replace(Scenario.pinned(), home=home, absolute_home=False).run(tmp_path)

    assert run.result.returncode != 0
    assert f"HOME is not an absolute path (HOME='{home}')" in run.result.stderr
    assert run.calls("curl") == [], "a relative HOME still reached the host"
    assert not (tmp_path / home / "Applications").exists()
