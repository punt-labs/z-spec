"""The CI ProB fetch: cached and pinned for specs, live for the installer.

The ProB archive host is a single university server; when it is down, every
CI leg that downloads the archive goes red. The ``specs`` job therefore
picks this OS's archive and SHA-256 pin once, caches the downloaded archive
under a key carrying that pin, fetches only on a miss, verifies every
archive -- cached or fresh -- against the pin before reading it, and saves
to the cache only after the archive proved good. The ``installer`` job must
NOT be cached: it exists to prove the live download a user's install does.

These tests read ``.github/workflows/test.yml`` as text (``Workflow``) and
check structure: step order, which shell branch a command sits in, how the
steps are wired to each other, and parity with install.sh. What the steps
DO is checked by running them: test_workflow_prob_pin_step.py,
test_workflow_probcli_steps.py (the install) and
test_workflow_probcli_verify_step.py.
"""

from __future__ import annotations

import re
from typing import Final

import pytest

from tests.install_sh_source import CurlFlags, InstallSh
from tests.workflow_source import Branch, Workflow

_HOST: Final[str] = "stups.hhu-hosting.de"
_CACHE_DIR: Final[str] = "${{ runner.temp }}/prob-archive"
_SELECT: Final[str] = "name: Select this OS's ProB archive and pin"
_INSTALL: Final[str] = "name: Install probcli"
_VERIFY: Final[str] = "name: Verify both binaries resolve"
_PIN_VARS: Final[dict[str, str]] = {
    "Linux": "PROB_SHA256_LINUX",
    "Darwin": "PROB_SHA256_MACOS",
}
_WF: Final[Workflow] = Workflow()
_VERSION: Final[str] = _WF.job_env("specs", "PROB_VERSION")


def _script(needle: str) -> list[str]:
    return _WF.step("specs", needle)[1].script()


# --- Structure ---------------------------------------------------------------


def test_both_gates_exist() -> None:
    assert {"specs", "installer"} <= _WF.jobs().keys(), sorted(_WF.jobs())


def test_host_and_curl_appear_only_in_the_miss_branch() -> None:
    script = _script(_INSTALL)
    branch = Branch.locate(script)
    miss = range(branch.else_ + 1, branch.fi)
    curl_lines = [i for i, ln in enumerate(script) if re.search(r"\bcurl\b", ln)]
    host_lines = [i for i, ln in enumerate(script) if _HOST in ln]
    assert curl_lines, "specs install step has no curl at all"
    outside = [script[i] for i in curl_lines + host_lines if i not in miss]
    assert not outside, f"ProB fetch outside the cache-miss branch: {outside}"
    assert _WF.job("specs").count(_HOST) == len(host_lines)


def test_pin_format_is_checked_before_the_hit_miss_branch() -> None:
    script = _script(_INSTALL)
    check = script.index('case "${EXPECTED_SHA256}" in')
    assert check < Branch.locate(script).if_


def test_pin_is_selected_once_before_the_cache_restore() -> None:
    select, step = _WF.step("specs", _SELECT)
    restore, _ = _WF.step("specs", "uses: actions/cache/restore@")
    assert step.field("id") == "prob-pin"
    assert select < restore
    assert all(f"${{{var}:?" in "\n".join(step.script()) for var in _PIN_VARS.values())
    for name in (_INSTALL, _VERIFY):
        # Read only through the prob-pin outputs, never chosen again.
        assert "${PROB_SHA256_" not in _WF.step("specs", name)[1].text


def test_restore_key_carries_os_version_and_the_selected_pin() -> None:
    _, restore = _WF.step("specs", "uses: actions/cache/restore@")
    assert restore.field("id") == "prob-cache"
    assert restore.field("path") == _CACHE_DIR
    assert restore.field("key") == (
        "prob-archive-${{ runner.os }}-${{ env.PROB_VERSION }}-"
        "${{ steps.prob-pin.outputs.sha256 }}"
    )


def test_install_step_env_is_wired_to_the_pin_and_cache_steps() -> None:
    step = _WF.step("specs", _INSTALL)[1]
    assert step.field("ARCHIVE") == "${{ steps.prob-pin.outputs.archive }}"
    assert step.field("EXPECTED_SHA256") == "${{ steps.prob-pin.outputs.sha256 }}"
    assert step.field("CACHE_HIT") == "${{ steps.prob-cache.outputs.cache-hit }}"
    assert step.field("CACHE_KEY") == (
        "${{ steps.prob-cache.outputs.cache-primary-key }}"
    )


def test_steps_run_under_githubs_default_bash() -> None:
    # No shell: and no defaults: means GitHub runs each block as
    # `bash -e {0}`, which is exactly how the behaviour tests below run it.
    assert "shell:" not in _WF.job("specs")
    assert "defaults:" not in _WF.job("specs")
    assert "defaults" not in _WF.top_level_keys()


@pytest.mark.parametrize("needle", [_SELECT, _INSTALL, _VERIFY])
def test_run_blocks_survive_extraction_whole(needle: str) -> None:
    # The runner strips each line; an expression GitHub substitutes, or a
    # heredoc whose indentation matters, would not survive that.
    script = _script(needle)
    assert not [ln for ln in script if "${{" in ln or "<<" in ln], script


def test_save_step_order_condition_key_and_path() -> None:
    order = [
        _WF.step("specs", n)[0]
        for n in (_SELECT, "cache/restore@", _INSTALL, _VERIFY, "cache/save@")
    ]
    make_test, _ = _WF.step("specs", "run: make test")
    assert order == sorted(order) and order[-1] < make_test, order
    save = _WF.step("specs", "uses: actions/cache/save@")[1]
    assert save.field("if") == "steps.prob-cache.outputs.cache-hit != 'true'"
    assert save.field("key") == "${{ steps.prob-cache.outputs.cache-primary-key }}"
    assert save.field("path") == _CACHE_DIR


def test_archive_path_is_inside_the_cached_directory() -> None:
    assigned = [ln for ln in _script(_INSTALL) if ln.startswith("ARCHIVE_PATH=")]
    shell_dir = _CACHE_DIR.replace("${{ runner.temp }}", "${RUNNER_TEMP}")
    assert assigned == [f'ARCHIVE_PATH="{shell_dir}/${{ARCHIVE}}"'], assigned


def test_cache_actions_are_sha_pinned_and_agree() -> None:
    shas: set[str] = set()
    for kind in ("restore", "save"):
        uses = _WF.step("specs", f"uses: actions/cache/{kind}@")[1].field("uses")
        match = re.fullmatch(
            rf"actions/cache/{kind}@([0-9a-f]{{40}}) # v\d+\.\d+\.\d+", uses
        )
        assert match, f"{kind} must be pinned to a full SHA with a version: {uses}"
        shas.add(match.group(1))
    assert len(shas) == 1, f"restore and save pinned to different commits: {shas}"


def test_prob_version_and_pins_match_install_sh() -> None:
    assert InstallSh().prob_version() == _VERSION
    for name, value in InstallSh().pins().items():
        assert _WF.job_env("specs", name) == value, f"{name} differs from install.sh"


@pytest.mark.parametrize("key", ["PROB_VERSION", *_PIN_VARS.values()])
def test_prob_values_live_in_the_job_env_once(key: str) -> None:
    defined = re.findall(rf"^\s+{key}:", _WF.job("specs"), re.M)
    assert len(defined) == 1, f"{key} defined {len(defined)}x in the specs job"
    assert key in _WF.job_env_keys("specs"), f"{key} is not in the job-level env:"


def test_specs_job_never_continues_on_error() -> None:
    assert "continue-on-error" not in _WF.job("specs")


def test_sha256_check_runs_on_both_paths_before_the_archive_is_read() -> None:
    script = _script(_INSTALL)
    fi = Branch.locate(script).fi
    hashed = [
        i for i, ln in enumerate(script) if 'shasum -a 256 < "${ARCHIVE_PATH}"' in ln
    ]
    # Any unzip/tar given the archive: a test (-tq), a listing (-Z1, -tzf),
    # or an extraction (-q ... -d, -xzf).
    reads = [
        i
        for i, ln in enumerate(script)
        if re.search(r'(unzip|tar) -\w+ "\$\{ARCHIVE_PATH\}"', ln)
    ]
    flags = {script[i].split('"${ARCHIVE_PATH}"')[0].split()[-1] for i in reads}
    assert {"-tq", "-Z1", "-tzf", "-q", "-xzf"} <= flags, flags
    assert len(hashed) == 1 and hashed[0] > fi, hashed
    assert hashed[0] < min(reads)


def test_specs_curl_matches_install_sh_flags() -> None:
    argv = _WF.step("specs", _INSTALL)[1].curl_argv()
    out = argv.index("-o")
    assert argv[0] == "curl" and argv[out + 1] == "${ARCHIVE_PATH}"
    assert argv[-1] == "${PROB_URL}"
    flags = CurlFlags.parse(argv[1:out] + argv[out + 2 : -1]).as_dict()
    expected = InstallSh().fetch_flags().with_flag("--retry-all-errors").as_dict()
    assert flags == expected, f"specs: {flags}\ninstall: {expected}"


def test_installer_is_never_cached() -> None:
    installer = _WF.job("installer")
    assert "actions/cache" not in installer and "prob-archive" not in installer
    assert "./install.sh --no-plugin" in installer
