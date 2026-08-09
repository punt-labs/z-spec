"""Tests for punt_zspec.prob_output, driven by real probcli transcripts.

Every fixture in ``tests/fixtures/probcli`` is verbatim output of an actual
probcli run. Nothing here is written from memory: probcli's output format is
the contract, and an invented fixture agrees with a broken parser.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from punt_zspec.prob_output import CoverageCensus, ProbOutput, UnreadableCoverage
from punt_zspec.types import CheckStatus

_FIXTURES = Path(__file__).parent / "fixtures" / "probcli"


def _output(name: str, returncode: int = 0) -> ProbOutput:
    return ProbOutput((_FIXTURES / name).read_text(encoding="utf-8"), returncode)


# ---------------------------------------------------------------------------
# The census probcli prints, read as probcli wrote it
# ---------------------------------------------------------------------------


def test_census_reports_the_real_names_and_counts() -> None:
    """Counts come off the census, not from a 1-or-0 the parser made up."""
    coverage = _output("model-check-covered.out").coverage()
    counts = {op.name: op.times_fired for op in coverage.operations}

    assert counts["ChangeCollection"] == 7
    assert counts["SelectResult"] == 3
    assert counts["ClearHighlight"] == 1
    assert counts["INITIALISATION"] == 1


def test_full_census_passes_the_coverage_check() -> None:
    check = _output("model-check-covered.out").coverage().check()

    assert check.name == "coverage"
    assert check.status == CheckStatus.passed
    assert check.detail == "13 operations covered"


def test_unreachable_operation_fails_and_is_named() -> None:
    """The mutant whose Freeze precondition no reachable state satisfies."""
    coverage = _output("model-check-uncovered.out").coverage()
    check = coverage.check()

    assert check.status == CheckStatus.failed
    assert "Freeze" in check.detail
    assert [op.name for op in coverage.operations if not op.covered] == ["Freeze"]


def test_broken_xi_frame_operation_fails_and_is_named() -> None:
    """The mutant whose RejectWithdraw frame makes the operation unsatisfiable."""
    check = _output("model-check-xi-uncovered.out").coverage().check()

    assert check.status == CheckStatus.failed
    assert "RejectWithdraw" in check.detail


def test_uncovered_operation_is_carried_with_a_zero_count() -> None:
    coverage = _output("model-check-uncovered.out").coverage()
    freeze = next(op for op in coverage.operations if op.name == "Freeze")

    assert freeze.times_fired == 0
    assert freeze.covered is False


def test_animate_census_is_read_too() -> None:
    coverage = _output("animate.out").coverage()

    assert [op.name for op in coverage.operations if not op.covered] == [
        "ClearHighlight"
    ]


# ---------------------------------------------------------------------------
# A missing or unreadable census is a failure, never a pass
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fixture", ["init.out", "cbc-assertions.out", "cbc-deadlock.out"]
)
def test_a_run_that_never_asked_reports_a_failed_check(fixture: str) -> None:
    coverage = _output(fixture).coverage()
    check = coverage.check()

    assert isinstance(coverage, UnreadableCoverage)
    assert check.status == CheckStatus.failed
    assert "-coverage" in check.detail
    assert coverage.operations == ()


def test_a_census_shorter_than_it_declares_is_unreadable() -> None:
    """A truncated list must not be read as full coverage."""
    truncated = (
        "[STATES (5),total:5,TOTAL_TRANSITIONS,17,"
        "COVERED_OPERATIONS (5),AcceptWithdraw:6,INITIALISATION:1,"
        "UNCOVERED_OPERATIONS (0)]"
    )
    coverage = CoverageCensus.read(truncated)

    assert isinstance(coverage, UnreadableCoverage)
    assert coverage.check().status == CheckStatus.failed
    assert "declares 5 entries but lists 2" in coverage.check().detail


def test_an_uncovered_headline_that_overstates_itself_is_unreadable() -> None:
    overstated = (
        "[STATES (5),total:5,TOTAL_TRANSITIONS,17,"
        "COVERED_OPERATIONS (1),AcceptWithdraw:6,"
        "UNCOVERED_OPERATIONS (2),Freeze]"
    )
    coverage = CoverageCensus.read(overstated)

    assert isinstance(coverage, UnreadableCoverage)
    assert "declares 2 entries but lists 1" in coverage.check().detail


def test_an_entry_without_a_count_is_unreadable() -> None:
    malformed = (
        "[STATES (5),total:5,TOTAL_TRANSITIONS,17,"
        "COVERED_OPERATIONS (1),AcceptWithdraw,"
        "UNCOVERED_OPERATIONS (0)]"
    )
    coverage = CoverageCensus.read(malformed)

    assert isinstance(coverage, UnreadableCoverage)
    assert "unreadable coverage entry: AcceptWithdraw" in coverage.check().detail


def test_a_census_with_no_covered_headline_is_unreadable() -> None:
    coverage = CoverageCensus.read("[STATES (5),total:5,UNCOVERED_OPERATIONS (0)]")

    assert isinstance(coverage, UnreadableCoverage)
    assert "no COVERED_OPERATIONS" in coverage.check().detail


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


def test_deadlock_free_marker_passes() -> None:
    check = _output("cbc-deadlock.out").check("cbc_deadlock")

    assert check.status == CheckStatus.passed
    assert check.detail == "deadlock-free"


def test_nonzero_exit_without_a_marker_fails() -> None:
    output = ProbOutput("probcli: cannot open file\n", 1)
    check = output.check("init")

    assert check.status == CheckStatus.failed
    assert "cannot open file" in check.detail


def test_incomplete_exploration_warns() -> None:
    output = ProbOutput("not all transitions were computed\n", 1)

    assert output.check("model_check").status == CheckStatus.warning


def test_version_is_unknown_when_the_run_announces_none() -> None:
    assert _output("init.out").version == "unknown"


def test_of_joins_stdout_and_stderr() -> None:
    completed = subprocess.CompletedProcess(
        args=["probcli"], returncode=0, stdout="out\n", stderr="err\n"
    )

    assert ProbOutput.of(completed).text == "out\nerr\n"
