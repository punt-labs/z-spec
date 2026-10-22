"""The CI ProB fetch: cached for the specs gate, live for the installer gate.

The ProB archive host is a single university server; when it is down, every
CI leg that downloads the archive goes red. The ``specs`` job therefore
caches the downloaded archive per OS and ProB version and only fetches on a
miss, with bounded curl retries. The ``installer`` job must NOT be cached:
it exists to prove the live download a user's install performs.

A workflow edit can silently undo either half, and nothing else would notice
until the next outage. These tests read ``.github/workflows/test.yml`` as
text, split it into its top-level jobs, and assert each half holds.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

_WORKFLOW: Final[Path] = (
    Path(__file__).resolve().parent.parent / ".github" / "workflows" / "test.yml"
)
_JOB_HEADER: Final[re.Pattern[str]] = re.compile(r"^  ([A-Za-z0-9_-]+):\s*$")
_CACHE_SUBACTION: Final[re.Pattern[str]] = re.compile(
    r"uses: actions/cache/(restore|save)@([0-9a-f]+) # v\d+\.\d+\.\d+$", re.MULTILINE
)


def _jobs() -> dict[str, str]:
    lines = _WORKFLOW.read_text(encoding="utf-8").splitlines()
    start = lines.index("jobs:") + 1
    jobs: dict[str, list[str]] = {}
    current: list[str] | None = None  # None until the first job header is seen
    for line in lines[start:]:
        if match := _JOB_HEADER.match(line):
            current = jobs.setdefault(match.group(1), [])
        elif current is not None:
            current.append(line)
    return {name: "\n".join(body) for name, body in jobs.items()}


def _prob_curl(job: str) -> str:
    match = re.search(r"curl [^\n]*(?:\\\n[^\n]*)*stups\.hhu-hosting\.de", job)
    assert match, "no curl fetch of the ProB archive found in the specs job"
    return match.group(0)


def test_both_gates_exist() -> None:
    jobs = _jobs()
    assert {"specs", "installer"} <= jobs.keys(), sorted(jobs)


def test_specs_restores_archive_keyed_on_os_and_prob_version() -> None:
    specs = _jobs()["specs"]

    assert 'PROB_VERSION: "' in specs, "PROB_VERSION must be job-level in specs"
    key = re.search(r"^\s+key: (prob-archive-.*)$", specs, re.MULTILINE)
    assert key, "specs job has no ProB archive cache key"
    assert "${{ runner.os }}" in key.group(1)
    assert "${{ env.PROB_VERSION }}" in key.group(1)


def test_cache_actions_are_sha_pinned_and_agree() -> None:
    pins = _CACHE_SUBACTION.findall(_jobs()["specs"])
    assert {kind for kind, _ in pins} == {"restore", "save"}, pins
    shas = {sha for _, sha in pins}
    assert len(shas) == 1, f"restore and save pinned to different commits: {pins}"
    assert len(next(iter(shas))) == 40, "cache action must be a full commit SHA"


def test_specs_downloads_only_on_cache_miss() -> None:
    specs = _jobs()["specs"]

    assert "CACHE_HIT: ${{ steps.prob-cache.outputs.cache-hit }}" in specs
    hit_branch = specs.index('if [ "${CACHE_HIT}" = "true" ]; then')
    assert hit_branch < specs.index("curl "), "curl must sit in the miss branch"
    assert "if: steps.prob-cache.outputs.cache-hit != 'true'" in specs


def test_slip_guard_runs_on_the_cached_path() -> None:
    specs = _jobs()["specs"]
    guard = specs.index("unsafe paths (absolute or ../)")

    # The guard and extraction read the same path the cache restores into,
    # after the hit/miss branch closes -- not only after a fresh download.
    assert specs.index("\n          fi\n", specs.index("CACHE_HIT}")) < guard
    assert 'unzip -Z1 "${ARCHIVE_PATH}"' in specs
    assert 'tar -tzf "${ARCHIVE_PATH}"' in specs


def test_specs_curl_has_bounded_retries() -> None:
    curl = _prob_curl(_jobs()["specs"])

    for flag in (
        "-fL",
        "--connect-timeout",
        "--retry 5",
        "--retry-connrefused",
        "--retry-all-errors",
        "--retry-max-time",
    ):
        assert flag in curl, f"specs ProB curl lost {flag}: {curl}"


def test_installer_is_never_cached() -> None:
    installer = _jobs()["installer"]

    assert "actions/cache" not in installer
    assert "prob-archive" not in installer
    assert "./install.sh --no-plugin" in installer
