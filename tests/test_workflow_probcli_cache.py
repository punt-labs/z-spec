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
branch a command sits in, the order of steps, where shared values are
defined, and parity of every shared value (version, pins, curl flags) with
install.sh. The second half runs the specs job's install and verify steps
themselves, offline, to check behaviour the text cannot show: what the
step does with a tampered, unpinned, missing, or hostile archive.
"""

from __future__ import annotations

import os
import re
import shlex
import shutil
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Final, final

import pytest

from tests.install_sh_source import CurlFlags, InstallSh, ProbArchive

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


def _job_env_block(job: str) -> list[str]:
    """Return the keys of the job-level env: that precedes steps:."""
    lines = job.splitlines()
    assert "    env:" in lines, "specs job has no job-level env:"
    assert "    steps:" in lines, "specs job has no steps:"
    start, end = lines.index("    env:"), lines.index("    steps:")
    assert start < end, "specs job env: must precede steps:"
    entry = re.compile(r"^      ([A-Z0-9_]+):")
    return [m.group(1) for ln in lines[start + 1 : end] if (m := entry.match(ln))]


def _workflow_curl(script: list[str]) -> list[str]:
    """Return the step's one curl command, up to any || failure handler."""
    starts = [i for i, ln in enumerate(script) if ln.startswith("curl ")]
    assert len(starts) == 1, f"expected one curl command in the step, got {starts}"
    parts: list[str] = []
    i = starts[0]
    while script[i].endswith("\\"):
        parts.append(script[i][:-1])
        i += 1
    parts.append(script[i])
    argv = shlex.split(" ".join(parts))
    return argv[: argv.index("||")] if "||" in argv else argv


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
    assert restore.field("key") == (
        "prob-archive-${{ runner.os }}-${{ env.PROB_VERSION }}-"
        "${{ runner.os == 'macOS' && env.PROB_SHA256_MACOS || env.PROB_SHA256_LINUX }}"
    ), "the key must carry the OS, the ProB version, and that OS's SHA-256 pin"


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


@pytest.mark.parametrize(
    "key", ["PROB_VERSION", "PROB_SHA256_LINUX", "PROB_SHA256_MACOS"]
)
def test_prob_values_live_in_the_job_env_once(key: str) -> None:
    # Job-level, so the cache key (a with: expression) and the install step
    # read one value. A step-level copy would leave the key on another.
    specs = _jobs()["specs"]
    defined = re.findall(rf"^\s+{key}:", specs, re.M)
    assert len(defined) == 1, f"{key} defined {len(defined)}x in the specs job"
    assert key in _job_env_block(specs), f"{key} is not in the specs job's env:"


def test_specs_job_never_continues_on_error() -> None:
    # continue-on-error on a pin-checking step would let a failed check fall
    # through to the cache save; nowhere in this job is that acceptable.
    assert "continue-on-error" not in _jobs()["specs"]


def test_sha256_check_runs_on_both_paths_before_the_archive_is_read() -> None:
    script = _install_script()
    branch = _hit_branch(script)
    hash_at = [
        i for i, ln in enumerate(script) if 'shasum -a 256 < "${ARCHIVE_PATH}"' in ln
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


# --- Behaviour: the specs job's install and verify steps, run offline --------
#
# Text checks prove where a command sits; they cannot prove what the step does
# with a hostile archive. These run the shipped ``run:`` blocks themselves
# under ``bash -e`` (how GitHub runs an unconfigured ``run:``), with the
# runner's environment supplied and a stub directory first on PATH: ``uname``
# reports the OS under test, ``curl`` serves a local archive or refuses, and
# ``tar``/``unzip``/``shasum`` log every call before running the real tool, so
# a test can prove a rejected archive was never listed or extracted.

_STEP_CURL: Final[str] = """#!/bin/sh
printf '%s\\n' "$*" >> "$LOGS/curl"
out=""
while [ $# -gt 0 ]; do
  if [ "$1" = "-o" ]; then out="$2"; shift; fi
  shift
done
if [ "$FETCH" = serve ]; then
  cp "$FIXTURE" "$out"
  exit 0
fi
echo "curl: (7) Failed to connect to stub host" >&2
exit 7
"""
_STEP_LOGGED: Final[str] = """#!/bin/sh
printf '%s\\n' "$*" >> "$LOGS/{name}"
exec '{real}' {args}
"""
_STEP_BROKEN: Final[str] = """#!/bin/sh
printf '%s\\n' "$*" >> "$LOGS/{name}"
echo "{name}: simulated read error" >&2
exit 1
"""
_STEP_UNAME: Final[str] = '#!/bin/sh\necho "$UNAME_S"\n'
_SYSTEMS: Final[list[str]] = ["Linux", "Darwin"]
_PIN_VARS: Final[dict[str, str]] = {
    "Linux": "PROB_SHA256_LINUX",
    "Darwin": "PROB_SHA256_MACOS",
}
_OTHER_PIN: Final[str] = "f" * 64  # the other OS's pin: valid, never matching
_CACHE_KEY: Final[str] = "prob-archive-Linux-1.15.1-stub"


def _tool(name: str) -> str:
    found = shutil.which(name)
    if found is None:
        pytest.fail(f"the host has no {name}, which the specs install step needs")
    return found


def _executable(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _step_env() -> dict[str, str]:
    return {"PROB_VERSION": _job_env(_jobs()["specs"], "PROB_VERSION")}


def _good(system: str) -> ProbArchive:
    return ProbArchive.with_probcli(system, _step_env()["PROB_VERSION"])


def _tampered(system: str) -> ProbArchive:
    """Same name and probcli as ``_good``, one extra member: another hash."""
    return ProbArchive.with_probcli(system, _step_env()["PROB_VERSION"], "ProB/x")


@final
@dataclass(frozen=True, slots=True)
class StepRun:
    """One execution of a specs step: its outcome and every logged tool call."""

    result: subprocess.CompletedProcess[str]
    runner_temp: Path
    logs: Path

    def calls(self, tool: str) -> list[list[str]]:
        log = self.logs / tool
        lines = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
        return [ln.split() for ln in lines]

    def archive_reads(self) -> list[list[str]]:
        """Every tar/unzip call: a list, test, or extraction of the archive."""
        return self.calls("tar") + self.calls("unzip")

    def extractions(self) -> list[list[str]]:
        tar = [c for c in self.calls("tar") if c and "x" in c[0]]
        unzip = [c for c in self.calls("unzip") if c and c[0] == "-q"]
        return tar + unzip

    def github_env(self) -> str:
        path = self.runner_temp / "github_env"
        return path.read_text(encoding="utf-8") if path.exists() else ""


@final
@dataclass(frozen=True, slots=True)
class InstallStep:
    """One run of the specs job's "Install probcli" step against a fixture.

    ``archive`` is what the restored cache holds (``cached``) or what the
    host serves on a miss; ``pin`` is the job-env pin for ``system``.
    """

    system: str
    archive: ProbArchive
    pin: str
    cache_hit: bool = False
    cached: bool = False
    fetch: str = "serve"
    broken_shasum: bool = False

    @classmethod
    def pinned(cls, archive: ProbArchive, *, cache_hit: bool) -> InstallStep:
        """A run whose pin is ``archive``'s own hash, cached on a hit."""
        return cls(archive.system, archive, archive.sha256(), cache_hit, cache_hit)

    def run(self, tmp_path: Path) -> StepRun:
        script = tmp_path / "step.sh"
        step = _one(_specs_steps(), "name: Install probcli")[1]
        script.write_text("\n".join(step.script()) + "\n", encoding="utf-8")
        runner, logs = tmp_path / "runner", tmp_path / "logs"
        logs.mkdir()
        if self.cached:
            self.archive.write(runner / "prob-archive")
        pins = dict.fromkeys(_PIN_VARS.values(), _OTHER_PIN)
        pins[_PIN_VARS[self.system]] = self.pin
        env = {
            **_step_env(),
            **pins,
            "PATH": f"{self._bin(tmp_path / 'bin')}{os.pathsep}{os.environ['PATH']}",
            "RUNNER_TEMP": str(runner),
            "GITHUB_ENV": str(runner / "github_env"),
            "GITHUB_REPOSITORY": "punt-labs/z-spec",
            "CACHE_HIT": "true" if self.cache_hit else "false",
            "CACHE_KEY": _CACHE_KEY,
            "LOGS": str(logs),
            "FETCH": self.fetch,
            "FIXTURE": str(self.archive.write(tmp_path / "served")),
            "UNAME_S": self.system,
        }
        result = subprocess.run(
            [_tool("bash"), "-e", str(script)],
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        return StepRun(result, runner, logs)

    def _bin(self, bin_dir: Path) -> Path:
        bin_dir.mkdir()
        _executable(bin_dir / "curl", _STEP_CURL)
        _executable(bin_dir / "uname", _STEP_UNAME)
        for name in ("tar", "unzip"):
            real = _tool(name)
            _executable(
                bin_dir / name, _STEP_LOGGED.format(name=name, real=real, args='"$@"')
            )
        if self.broken_shasum:
            _executable(bin_dir / "shasum", _STEP_BROKEN.format(name="shasum"))
        elif shutil.which("shasum") is not None:
            real, args = _tool("shasum"), '"$@"'
            _executable(
                bin_dir / "shasum",
                _STEP_LOGGED.format(name="shasum", real=real, args=args),
            )
        else:  # a Linux host without perl's shasum: sha256sum reads stdin alike
            real = _tool("sha256sum")
            _executable(
                bin_dir / "shasum",
                _STEP_LOGGED.format(name="shasum", real=real, args=""),
            )
        return bin_dir


@pytest.mark.parametrize("system", _SYSTEMS)
def test_step_cache_hit_with_a_tampered_archive_fails_closed(
    tmp_path: Path, system: str
) -> None:
    good = _good(system)
    step = InstallStep(system, _tampered(system), good.sha256(), True, True)
    run = step.run(tmp_path)

    err = run.result.stderr
    assert run.result.returncode != 0
    assert f"FATAL: SHA-256 mismatch for {good.name}" in err
    assert f"cache key {_CACHE_KEY}" in err
    assert f"gh cache delete '{_CACHE_KEY}'" in err
    assert run.archive_reads() == [], "a tampered cached archive was read"
    assert run.calls("curl") == [], "a cache hit contacted the host"
    assert "PROBCLI=" not in run.github_env()


@pytest.mark.parametrize("system", _SYSTEMS)
def test_step_cache_miss_serving_a_tampered_archive_fails_closed(
    tmp_path: Path, system: str
) -> None:
    good = _good(system)
    run = InstallStep(system, _tampered(system), good.sha256()).run(tmp_path)

    err = run.result.stderr
    assert run.result.returncode != 0
    assert f"FATAL: SHA-256 mismatch for {good.name}" in err
    assert f"download https://{_HOST}/" in err
    assert run.archive_reads() == [], "a tampered download was read"
    assert "PROBCLI=" not in run.github_env()


@pytest.mark.parametrize("system", _SYSTEMS)
def test_step_shipped_pin_never_installs_the_fixture(
    tmp_path: Path, system: str
) -> None:
    # The shipped value, whatever it is: a placeholder today ("no verified
    # pin"), a real hash once one lands ("mismatch" against this fixture).
    shipped = _job_env(_jobs()["specs"], _PIN_VARS[system])
    run = InstallStep(system, _good(system), shipped, True, True).run(tmp_path)

    err = run.result.stderr
    assert run.result.returncode != 0
    assert "no verified SHA-256 pin" in err or "SHA-256 mismatch" in err, err
    assert run.archive_reads() == []
    assert "PROBCLI=" not in run.github_env()


@pytest.mark.parametrize("system", _SYSTEMS)
@pytest.mark.parametrize(
    "pin",
    ["PLACEHOLDER-unverified-awaiting-download-from-prob-host", "", "A" * 64, "0" * 63],
    ids=["placeholder", "empty", "uppercase", "short"],
)
def test_step_non_hash_pin_is_named_as_such(
    tmp_path: Path, system: str, pin: str
) -> None:
    run = InstallStep(system, _good(system), pin, True, True).run(tmp_path)

    err = run.result.stderr
    assert run.result.returncode != 0
    assert "FATAL: no verified SHA-256 pin" in err
    assert f"pin is not 64 lowercase hex digits (value: {pin})" in err
    assert "SHA-256 mismatch" not in err
    assert run.archive_reads() == []


def test_step_cache_hit_with_no_archive_fails(tmp_path: Path) -> None:
    good = _good("Linux")
    run = InstallStep("Linux", good, good.sha256(), cache_hit=True).run(tmp_path)

    err = run.result.stderr
    assert run.result.returncode != 0
    assert "FATAL: cache hit but" in err
    assert "is missing" in err
    assert f"gh cache delete '{_CACHE_KEY}'" in err
    assert run.calls("curl") == []


@pytest.mark.parametrize("system", _SYSTEMS)
@pytest.mark.parametrize("cache_hit", [True, False], ids=["hit", "miss"])
def test_step_matching_pin_installs_probcli(
    tmp_path: Path, system: str, cache_hit: bool
) -> None:
    run = InstallStep.pinned(_good(system), cache_hit=cache_hit).run(tmp_path)

    assert run.result.returncode == 0, run.result.stderr
    probcli = run.runner_temp / "ProB" / "ProB" / "probcli"
    assert f"PROBCLI={probcli}\n" in run.github_env()
    assert f"PROB_HOME={probcli.parent}\n" in run.github_env()
    assert probcli.is_file()
    assert len(run.calls("curl")) == (0 if cache_hit else 1)


def test_step_cache_miss_logs_the_url_it_fetches(tmp_path: Path) -> None:
    good = _good("Linux")
    run = InstallStep.pinned(good, cache_hit=False).run(tmp_path)
    url = f"https://{_HOST}/downloads/prob/tcltk/releases/"
    url += f"{_step_env()['PROB_VERSION']}/{good.name}"

    assert f"cache miss (cache-hit='false', key {_CACHE_KEY}) -- downloading {url}" in (
        run.result.stdout
    )
    assert run.calls("curl")[0][-1] == url


@pytest.mark.parametrize("system", _SYSTEMS)
@pytest.mark.parametrize("member", ["../escaped", "ProB/../../escaped"])
def test_step_refuses_a_pinned_archive_with_an_escaping_member(
    tmp_path: Path, system: str, member: str
) -> None:
    # The pin only proves the archive is the one the publisher shipped; the
    # slip guard is what stops a hostile publisher's ../ member.
    archive = ProbArchive.with_probcli(system, _step_env()["PROB_VERSION"], member)
    run = InstallStep.pinned(archive, cache_hit=True).run(tmp_path)

    assert run.result.returncode != 0
    assert "contains unsafe paths (absolute or ../)" in run.result.stderr
    assert run.extractions() == [], "an archive with a ../ member was extracted"
    assert not (run.runner_temp / "escaped").exists()
    assert "PROBCLI=" not in run.github_env()


def test_step_failing_hash_tool_is_not_a_mismatch(tmp_path: Path) -> None:
    good = _good("Linux")
    step = InstallStep("Linux", good, good.sha256(), True, True, broken_shasum=True)
    run = step.run(tmp_path)

    err = run.result.stderr
    assert run.result.returncode != 0
    assert "FATAL: could not compute SHA-256 (sha tool failed)" in err
    assert "SHA-256 mismatch" not in err
    assert run.archive_reads() == []


def test_step_download_failure_names_the_url(tmp_path: Path) -> None:
    good = _good("Linux")
    run = InstallStep("Linux", good, good.sha256(), fetch="refuse").run(tmp_path)

    assert run.result.returncode != 0
    assert f"FATAL: ProB download failed: https://{_HOST}/" in run.result.stderr
    assert good.name in run.result.stderr
    assert run.archive_reads() == []


@final
@dataclass(frozen=True, slots=True)
class VerifyStep:
    """One run of the "Verify both binaries resolve" step with a stub probcli."""

    probcli: str  # the stub probcli's shell body

    def run(self, tmp_path: Path) -> subprocess.CompletedProcess[str]:
        script = tmp_path / "step.sh"
        step = _one(_specs_steps(), "name: Verify both binaries resolve")[1]
        script.write_text("\n".join(step.script()) + "\n", encoding="utf-8")
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        _executable(bin_dir / "fuzz", "#!/bin/sh\nexit 0\n")
        probcli = tmp_path / "probcli"
        _executable(probcli, f"#!/bin/sh\n{self.probcli}\n")
        env = {
            **_step_env(),
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "PROBCLI": str(probcli),
        }
        return subprocess.run(
            [_tool("bash"), "-e", str(script)],
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )


def test_verify_step_accepts_the_pinned_version(tmp_path: Path) -> None:
    version = _step_env()["PROB_VERSION"]
    result = VerifyStep(f"echo 'ProB version {version}'").run(tmp_path)
    assert result.returncode == 0, result.stderr


def test_verify_step_rejects_a_longer_version(tmp_path: Path) -> None:
    version = _step_env()["PROB_VERSION"]
    result = VerifyStep(f"echo 'ProB version {version}0'").run(tmp_path)

    assert result.returncode != 0
    assert f"FATAL: expected probcli {version}, got: {version}0" in result.stderr


def test_verify_step_shows_why_probcli_would_not_run(tmp_path: Path) -> None:
    body = "echo 'error while loading shared libraries: libtcl8.6.so' >&2; exit 127"
    result = VerifyStep(body).run(tmp_path)

    assert result.returncode != 0
    assert "-version failed; its output:" in result.stderr
    assert "libtcl8.6.so" in result.stderr
