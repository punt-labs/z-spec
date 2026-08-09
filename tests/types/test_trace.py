"""Tests for punt_zspec.types.trace."""

from __future__ import annotations

from punt_zspec.types import CounterExample, TraceStep


def test_trace_step_to_dict() -> None:
    step = TraceStep(step_number=2, operation="INITIALISATION", state={"count": "2"})

    assert step.to_dict() == {
        "step_number": 2,
        "operation": "INITIALISATION",
        "state": {"count": "2"},
    }


def test_counter_example_nests_its_steps() -> None:
    example = CounterExample(
        steps=[TraceStep(1, "SETUP_CONSTANTS", {}), TraceStep(2, "INITIALISATION", {})],
        violation="deadlock",
    )

    assert example.to_dict() == {
        "steps": [
            {"step_number": 1, "operation": "SETUP_CONSTANTS", "state": {}},
            {"step_number": 2, "operation": "INITIALISATION", "state": {}},
        ],
        "violation": "deadlock",
    }


def test_a_trace_with_no_steps_still_carries_its_violation() -> None:
    assert CounterExample(steps=[], violation="invariant violated").to_dict() == {
        "steps": [],
        "violation": "invariant violated",
    }
