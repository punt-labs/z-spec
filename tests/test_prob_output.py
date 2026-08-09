"""Tests for punt_zspec.prob_output, driven by real probcli transcripts.

Every fixture in ``tests/fixtures/probcli`` is verbatim output of an actual
probcli run. Nothing here is written from memory: probcli's output format is
the contract, and an invented fixture agrees with a broken parser.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from punt_zspec.prob_output import ProbOutput
from punt_zspec.types import CheckStatus

_FIXTURES = Path(__file__).parent / "fixtures" / "probcli"


def _output(name: str, returncode: int = 0) -> ProbOutput:
    return ProbOutput((_FIXTURES / name).read_text(encoding="utf-8"), returncode)


# ---------------------------------------------------------------------------
# The rest of what one run asserts
# ---------------------------------------------------------------------------


def test_clean_exploration_passes_with_its_counts() -> None:
    check = _output("model-check-covered.out").check("model_check")

    assert check.status == CheckStatus.passed
    assert check.detail == "8 states, 39 transitions"


def test_counts_are_read_off_the_transcript() -> None:
    output = _output("model-check-covered.out")

    assert output.states_analysed == 8
    assert output.transitions_fired == 39


def test_declared_operations_come_from_the_load_banner() -> None:
    assert _output("init.out").declared_operations == (
        "EnterQuery",
        "ClearQuery",
        "ReceiveResults",
        "ReceiveEmpty",
        "ReceiveError",
        "SelectResult",
        "HighlightResult",
        "ClearHighlight",
        "CloseDetail",
        "ProgrammaticClear",
        "ChangeCollection",
    )


def test_counter_example_is_parsed_from_the_real_trace() -> None:
    """probcli exits 0 on a counter-example, so the text is the only signal.

    The transcript was captured at returncode 0 deliberately. A parser leaning
    on the exit status would call this run clean.
    """
    output = ProbOutput(
        (_FIXTURES / "model-check-counter-example.out").read_text(encoding="utf-8"),
        0,
    )
    example = output.counter_example()

    check = output.check("model_check")
    assert check.status == CheckStatus.failed
    assert check.detail == "deadlock"
    assert example is not None
    assert example.violation == "deadlock"
    assert [(s.step_number, s.operation) for s in example.steps] == [
        (1, "INITIALISATION")
    ]


def test_full_coverage_does_not_mask_a_counter_example() -> None:
    """probcli prints ALL OPERATIONS COVERED mid-run, then finds the deadlock.

    Every operation fires and the census is clean, so coverage genuinely
    passes — and the run still failed. A verdict taken from the coverage
    banner would call this specification sound.
    """
    output = _output("model-check-covered-then-deadlock.out")

    assert "ALL OPERATIONS COVERED" in output.text
    assert output.coverage().check().status == CheckStatus.passed
    assert output.check("model_check").status == CheckStatus.failed
    assert output.check("model_check").detail == "deadlock"


def test_a_deadlocked_run_fails_on_both_counts_independently() -> None:
    """The probe deadlocks AND leaves Step unfired; neither answer implies the other."""
    output = _output("model-check-counter-example.out")

    assert output.check("model_check").status == CheckStatus.failed
    assert output.coverage().check().status == CheckStatus.failed
    assert "Step" in output.coverage().check().detail


def test_a_clean_run_has_no_counter_example() -> None:
    assert _output("model-check-covered.out").counter_example() is None


def test_an_uncertified_run_is_neither_passed_nor_failed() -> None:
    """probcli found nothing and did not finish looking; those differ.

    "No counter example found" is a claim over ALL reachable states, so a
    truncated run cannot establish it — but the specification is not thereby
    broken either. The verdict is warning, and it names the bound to raise.
    """
    check = _output("model-check-incomplete.out").check("model_check")

    assert check.status == CheckStatus.warning
    assert "not certified complete" in check.detail
    assert "raise MAX_OPERATIONS" in check.detail


def test_an_incomplete_run_can_hide_a_real_violation() -> None:
    """The reason the model-check verdict must not pass when uncertified.

    ``specs/hidden-deadlock-bad.tex`` has a genuine deadlock: at
    MAX_OPERATIONS=2000 probcli finds it. This transcript is the same
    specification at MAX_OPERATIONS=3, where the transition reaching it was
    never computed. probcli reports no counter-example, ``deadlocked:0``,
    ``ALL OPERATIONS COVERED``, and exits 0 — every signal a clean run gives.
    Only the incompleteness marker distinguishes the two.
    """
    output = _output("model-check-hidden-deadlock.out")

    assert "No counter example found" in output.text
    assert "deadlocked:0" in output.text
    assert output.counter_example() is None
    assert output.check("model_check").status is not CheckStatus.passed
    assert output.check("model_check").status == CheckStatus.warning


def test_the_coverage_half_of_a_hiding_run_is_still_sound() -> None:
    """Coverage is existential, so truncation cannot make it over-report.

    The same run that hides a deadlock reports its census honestly: every
    operation it names did fire. Failing the whole report on incompleteness
    must not discard that.
    """
    coverage = _output("model-check-hidden-deadlock.out").coverage()

    assert coverage.check().status == CheckStatus.passed
    assert {op.name for op in coverage.operations} == {
        "Step",
        "Hold",
        "INITIALISATION",
    }


def test_an_uncertified_run_still_reports_the_coverage_it_saw() -> None:
    """Coverage is existential and monotone, so truncation cannot over-report it.

    More exploration only ever adds covered operations. A clean census from a
    truncated run is therefore sound — and this run's census is not clean, so
    the operation named here is the one the run did not reach.
    """
    coverage = _output("model-check-incomplete.out").coverage()

    assert [op.name for op in coverage.operations if not op.covered] == ["EndSession"]
    assert coverage.operations  # the census was read, not discarded


def test_a_failing_init_fails_although_probcli_exits_zero() -> None:
    """The -init step emits no counter-example, no census, and no marker.

    Without probcli's own error tally its verdict would rest on an exit status
    probcli does not set: this transcript is INITIALISATION FAILS at exit 0.
    A specification that cannot reach an initial state must not pass.
    """
    output = _output("init-fails.out")
    check = output.check("init")

    assert "INITIALISATION FAILS" in output.text
    assert check.status == CheckStatus.failed
    assert "initialisation_fails" in check.detail


@pytest.mark.parametrize(
    "fixture", ["init.out", "model-check-covered.out", "cbc-deadlock.out"]
)
def test_a_clean_run_tallies_no_errors(fixture: str) -> None:
    """probcli prints the tally only when something went wrong."""
    assert "Total Errors" not in _output(fixture).text
    assert _output(fixture).check("run").status == CheckStatus.passed


def test_a_warning_only_run_is_not_read_as_an_error() -> None:
    """Total Errors: 0, Warnings: 1 must reach the incompleteness branch."""
    check = _output("model-check-incomplete.out").check("model_check")

    assert "Total Errors: 0" in _output("model-check-incomplete.out").text
    assert check.status == CheckStatus.warning


def test_deadlock_free_marker_passes() -> None:
    check = _output("cbc-deadlock.out").check("cbc_deadlock")

    assert check.status == CheckStatus.passed
    assert check.detail == "deadlock-free"


def test_nonzero_exit_without_a_marker_fails() -> None:
    output = ProbOutput("probcli: cannot open file\n", 1)
    check = output.check("init")

    assert check.status == CheckStatus.failed
    assert "cannot open file" in check.detail


def test_a_counter_example_outranks_incompleteness() -> None:
    """Finding one is existential — a truncated run that found it still found it."""
    output = ProbOutput(
        "*** COUNTER EXAMPLE FOUND ***\ndeadlock\n 1: INITIALISATION\n"
        "! model_check_incomplete\n",
        0,
    )

    assert output.check("model_check").status == CheckStatus.failed


def test_version_is_unknown_when_the_run_announces_none() -> None:
    assert _output("init.out").version == "unknown"


def test_of_joins_stdout_and_stderr() -> None:
    completed = subprocess.CompletedProcess(
        args=["probcli"], returncode=0, stdout="out\n", stderr="err\n"
    )

    assert ProbOutput.of(completed).text == "out\nerr\n"
