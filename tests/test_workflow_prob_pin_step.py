"""The specs job's prob-pin step, run offline: which archive and pin it outputs.

Each test runs the shipped ``run:`` block through ``workflow_step_runner``
under ``bash -e``, as GitHub would, and reads what it wrote to
GITHUB_OUTPUT -- the values the cache key and the install step are built
from, so a pin that can never verify an archive must stop here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pytest

from tests.prob_archive import ProbArchive
from tests.workflow_step_runner import BAD_PINS, PIN_VARS, PROB_VERSION, StepHarness

# The malformed pins the select step names as such: an empty one fails
# earlier (${VAR:?}), and a two-line one gets its own message.
_MALFORMED: Final[dict[str, str]] = {
    k: v for k, v in BAD_PINS.items() if k not in ("empty", "two-lines")
}


def _name(system: str) -> str:
    return ProbArchive.with_probcli(system, PROB_VERSION).name


@pytest.mark.parametrize(
    ("runner_os", "system"), [("Linux", "Linux"), ("macOS", "Darwin")]
)
def test_select_outputs_this_os_archive_and_pin(
    tmp_path: Path, runner_os: str, system: str
) -> None:
    pins = {"PROB_SHA256_LINUX": "1" * 64, "PROB_SHA256_MACOS": "2" * 64}
    run = StepHarness.select(runner_os, pins).run(tmp_path)
    assert run.result.returncode == 0, run.result.stderr
    archive, pin = _name(system), pins[PIN_VARS[system]]
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
    pins = dict.fromkeys(PIN_VARS.values(), pin)
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
    pins = dict.fromkeys(PIN_VARS.values(), pin)
    run = StepHarness.select(runner_os, pins).run(tmp_path)
    err = run.result.stderr
    assert run.result.returncode != 0
    assert f"FATAL: no verified SHA-256 pin for {_name(system)}" in err
    assert f"pin is not 64 lowercase hex digits (value: {pin})" in err
    assert run.file("github_output") == ""
