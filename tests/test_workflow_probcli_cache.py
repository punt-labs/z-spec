"""The CI ProB fetch: cached and pinned for specs, live for the installer.

The ProB archive host is a single university server; when it is down, every
CI leg that downloads the archive goes red. The ``specs`` job therefore
caches the downloaded archive per OS and ProB version and only fetches on a
miss, verifies every archive -- cached or fresh -- against a SHA-256 pin
before reading it, and saves to the cache only after the archive proved
good. The ``installer`` job must NOT be cached: it exists to prove the live
download a user's install performs.

A workflow edit can silently undo any of that, and nothing else would notice
until the next outage or the next tampered archive. These tests read
``.github/workflows/test.yml`` as text, with ``#`` comment lines removed so
prose can never satisfy an assertion, and check structure: which shell
branch a command sits in, the order of steps, and parity of every shared
value (version, pins, curl flags) with install.sh.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from tests.install_sh_source import CurlFlags, InstallSh

_WORKFLOW: Final[Path] = (
    Path(__file__).resolve().parent.parent / ".github" / "workflows" / "test.yml"
)
_JOB_HEADER: Final[re.Pattern[str]] = re.compile(r"^  ([A-Za-z0-9_-]+):\s*$")
_HOST: Final[str] = "stups.hhu-hosting.de"
_HIT_TEST: Final[str] = 'if [ "${CACHE_HIT}" = "true" ]; then'
_CACHE_DIR: Final[str] = "${{ runner.temp }}/prob-archive"


def _code(text: str) -> str:
    """Drop ``#`` comment lines: only YAML and shell code may satisfy a test."""
    return "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))


def _jobs() -> dict[str, str]:
    lines = _code(_WORKFLOW.read_text(encoding="utf-8")).splitlines()
    assert "jobs:" in lines, "test.yml has no top-level jobs: key"
    jobs: dict[str, list[str]] = {}
    current: list[str] | None = None  # None until the first job header is seen
    for line in lines[lines.index("jobs:") + 1 :]:
        if match := _JOB_HEADER.match(line):
            current = jobs.setdefault(match.group(1), [])
        elif current is not None:
            current.append(line)
    return {name: "\n".join(body) for name, body in jobs.items()}


@dataclass(frozen=True, slots=True)
class Step:
    """One ``- ...`` entry of a job's steps list, as raw YAML text."""

    text: str

    def field(self, key: str) -> str:
        match = re.search(rf"^\s*(?:- )?{re.escape(key)}: (.*)$", self.text, re.M)
        assert match, f"step has no {key}: field:\n{self.text}"
        return match.group(1).strip()

    def has(self, needle: str) -> bool:
        return needle in self.text

    def script(self) -> list[str]:
        """Return the step's ``run: |`` body, one stripped line per entry."""
        lines = self.text.splitlines()
        start = next((i for i, ln in enumerate(lines) if ln.strip() == "run: |"), None)
        assert start is not None, f"step has no `run: |` block:\n{self.text}"
        return [ln.strip() for ln in lines[start + 1 :] if ln.strip()]


def _steps(job: str) -> list[Step]:
    lines = job.splitlines()
    first = lines.index("    steps:") + 1
    indent = len(lines[first]) - len(lines[first].lstrip())
    marker = " " * indent + "- "
    steps: list[list[str]] = []
    for line in lines[first:]:
        if line.startswith(marker):
            steps.append([line])
        elif steps:
            steps[-1].append(line)
    return [Step("\n".join(s)) for s in steps]


def _specs_steps() -> list[Step]:
    return _steps(_jobs()["specs"])


def _one(steps: list[Step], needle: str) -> tuple[int, Step]:
    hits = [(i, s) for i, s in enumerate(steps) if s.has(needle)]
    assert len(hits) == 1, f"expected exactly one specs step with {needle!r}"
    return hits[0]


def _install_script() -> list[str]:
    return _one(_specs_steps(), "name: Install probcli")[1].script()


@dataclass(frozen=True, slots=True)
class Branch:
    """Line indices of the cache-hit ``if``, its ``else``, and its ``fi``."""

    if_: int
    else_: int
    fi: int


def _hit_branch(script: list[str]) -> Branch:
    """Locate the cache-hit if/else/fi by shell nesting, not by indentation."""
    assert script.count(_HIT_TEST) == 1, f"expected one `{_HIT_TEST}` line"
    start = script.index(_HIT_TEST)
    depth, else_ = 0, None
    for i in range(start, len(script)):
        line = script[i]
        if line.startswith("if ") and line.endswith("then"):
            depth += 1
        elif line == "else" and depth == 1:
            else_ = i
        elif line == "fi":
            depth -= 1
            if depth == 0:
                assert else_ is not None, "cache-hit if has no else (miss) branch"
                return Branch(start, else_, i)
    raise AssertionError("cache-hit if is never closed by fi")


def _job_env(job: str, key: str) -> str:
    found = re.findall(rf'^\s+{re.escape(key)}: "([^"]*)"$', job, re.M)
    assert len(found) == 1, f"expected {key} defined once in the job, got {found}"
    return str(found[0])


def _workflow_curl(script: list[str]) -> list[str]:
    starts = [i for i, ln in enumerate(script) if ln.startswith("curl ")]
    assert len(starts) == 1, f"expected one curl command in the step, got {starts}"
    parts: list[str] = []
    i = starts[0]
    while script[i].endswith("\\"):
        parts.append(script[i][:-1])
        i += 1
    parts.append(script[i])
    return shlex.split(" ".join(parts))


def test_both_gates_exist() -> None:
    jobs = _jobs()
    assert {"specs", "installer"} <= jobs.keys(), sorted(jobs)


def test_host_and_curl_appear_only_in_the_miss_branch() -> None:
    script = _install_script()
    branch = _hit_branch(script)
    miss = range(branch.else_ + 1, branch.fi)

    curl_lines = [i for i, ln in enumerate(script) if re.search(r"\bcurl\b", ln)]
    host_lines = [i for i, ln in enumerate(script) if _HOST in ln]
    assert curl_lines, "specs install step has no curl at all"
    outside = [script[i] for i in curl_lines + host_lines if i not in miss]
    assert not outside, f"ProB fetch outside the cache-miss branch: {outside}"
    # And nowhere else in the job: a hit must make zero requests to the host.
    assert _jobs()["specs"].count(_HOST) == len(host_lines)


def test_cache_miss_is_logged_with_the_cache_hit_value() -> None:
    script = _install_script()
    branch = _hit_branch(script)
    miss = script[branch.else_ + 1 : branch.fi]
    assert any("cache miss" in ln and "cache-hit=" in ln for ln in miss), miss


def test_restore_key_is_os_and_prob_version() -> None:
    _, restore = _one(_specs_steps(), "uses: actions/cache/restore@")
    assert restore.field("id") == "prob-cache"
    assert restore.field("path") == _CACHE_DIR
    assert (
        restore.field("key") == "prob-archive-${{ runner.os }}-${{ env.PROB_VERSION }}"
    )


def test_save_step_order_condition_key_and_path() -> None:
    steps = _specs_steps()
    restore, _ = _one(steps, "uses: actions/cache/restore@")
    install, _ = _one(steps, "name: Install probcli")
    version, _ = _one(steps, '"${PROBCLI}" -version')
    save, save_step = _one(steps, "uses: actions/cache/save@")
    make_test, _ = _one(steps, "run: make test")

    assert restore < install < version < save < make_test, (
        f"specs step order must be restore < install < probcli -version < save "
        f"< make test, got {restore=} {install=} {version=} {save=} {make_test=}"
    )
    assert save_step.field("if") == "steps.prob-cache.outputs.cache-hit != 'true'"
    assert save_step.field("key") == "${{ steps.prob-cache.outputs.cache-primary-key }}"
    assert save_step.field("path") == _CACHE_DIR


def test_archive_path_is_inside_the_cached_directory() -> None:
    script = _install_script()
    assigned = [ln for ln in script if ln.startswith("ARCHIVE_PATH=")]
    shell_dir = _CACHE_DIR.replace("${{ runner.temp }}", "${RUNNER_TEMP}")
    assert assigned == [f'ARCHIVE_PATH="{shell_dir}/${{ARCHIVE}}"'], assigned


def test_cache_actions_are_sha_pinned_and_agree() -> None:
    steps = _specs_steps()
    pins = {
        kind: _one(steps, f"uses: actions/cache/{kind}@")[1].field("uses")
        for kind in ("restore", "save")
    }
    shas: set[str] = set()
    for kind, uses in pins.items():
        match = re.fullmatch(
            rf"actions/cache/{kind}@([0-9a-f]{{40}}) # v\d+\.\d+\.\d+", uses
        )
        assert match, f"{kind} must be pinned to a full SHA with a version: {uses}"
        shas.add(match.group(1))
    assert len(shas) == 1, f"restore and save pinned to different commits: {pins}"


def test_prob_version_defined_once_and_matches_install_sh() -> None:
    specs = _jobs()["specs"]
    assert specs.count("PROB_VERSION:") == 1, "PROB_VERSION overridden in specs"
    assert _job_env(specs, "PROB_VERSION") == InstallSh().prob_version()


def test_sha256_pins_match_install_sh() -> None:
    specs = _jobs()["specs"]
    for name, value in InstallSh().pins().items():
        assert _job_env(specs, name) == value, f"{name} differs from install.sh"


def test_sha256_check_runs_on_both_paths_before_the_archive_is_read() -> None:
    script = _install_script()
    branch = _hit_branch(script)
    hash_at = [
        i for i, ln in enumerate(script) if 'shasum -a 256 "${ARCHIVE_PATH}"' in ln
    ]
    reads = [
        i
        for i, ln in enumerate(script)
        if re.search(r'(unzip|tar) -\w*[tZx]\w* "\$\{ARCHIVE_PATH\}"', ln)
        or ln.startswith("if printf '%s\\n' \"${LISTING}\"")
    ]

    assert len(hash_at) == 1, f"expected one shasum of the archive, got {hash_at}"
    assert hash_at[0] > branch.fi, "hash check must run after hit/miss, on both"
    assert reads, "no listing/extraction found in the install step"
    assert hash_at[0] < min(reads), "hash check must precede any read of the archive"
    assert any("PROB_SHA256_LINUX" in ln for ln in script[: branch.if_]) and any(
        "PROB_SHA256_MACOS" in ln for ln in script[: branch.if_]
    )
    mismatch = next(
        (i for i, ln in enumerate(script) if "SHA-256 mismatch" in ln), None
    )
    assert mismatch is not None, "no SHA-256 mismatch FATAL in the install step"
    tail = script[mismatch : mismatch + 6]
    for field in ("expected:", "actual:", "${SOURCE}", "exit 1"):
        assert any(field in ln for ln in tail), f"mismatch FATAL lacks {field}"


def test_corrupt_archive_diagnostics_name_source_and_file_type() -> None:
    script = _install_script()
    branch = _hit_branch(script)
    hit = script[branch.if_ + 1 : branch.else_]

    assert any(ln.startswith("HINT=") and "gh cache delete" in ln for ln in hit)
    assert any('unzip -tq "${ARCHIVE_PATH}"' in ln for ln in script)
    fatal = [ln for ln in script if "is not a valid archive" in ln]
    assert fatal, "no FATAL for a corrupt archive"
    assert "${SOURCE}" in fatal[0]
    assert "file -b" in fatal[0]
    assert "${HINT}" in fatal[0]


def test_specs_curl_matches_install_sh_flags() -> None:
    argv = _workflow_curl(_install_script())

    assert argv[0] == "curl"
    out = argv.index("-o")
    assert argv[out + 1] == "${ARCHIVE_PATH}"
    assert argv[-1] == "${PROB_URL}"
    flags = CurlFlags.parse(argv[1:out] + argv[out + 2 : -1]).as_dict()
    expected = InstallSh().fetch_flags().with_flag("--retry-all-errors").as_dict()
    assert flags == expected, (
        f"specs curl flags drifted from install.sh:\n  specs:   {flags}\n"
        f"  install: {expected}"
    )


def test_probcli_version_is_checked_exactly() -> None:
    _, step = _one(_specs_steps(), '"${PROBCLI}" -version')
    script = step.script()
    assert any('[ "${PROB_VER}" != "${PROB_VERSION}" ]' in ln for ln in script)


def test_installer_is_never_cached() -> None:
    installer = _jobs()["installer"]

    assert "actions/cache" not in installer
    assert "prob-archive" not in installer
    assert "./install.sh --no-plugin" in installer
