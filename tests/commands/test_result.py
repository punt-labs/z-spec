"""Unit tests for the CommandResult envelope and its failure types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from punt_zspec.commands.result import (
    CommandError,
    CommandFailure,
    CommandResult,
)


@dataclass(frozen=True, slots=True)
class _Payload:
    """A minimal JsonObject payload for exercising the envelope."""

    value: int

    def to_dict(self) -> dict[str, Any]:
        return {"value": self.value}


def test_ok_carries_payload() -> None:
    result: CommandResult[_Payload] = CommandResult.ok(_Payload(7))

    assert result.is_ok
    assert result.error is None
    assert result.unwrap() == _Payload(7)


def test_ok_serializes_payload() -> None:
    result: CommandResult[_Payload] = CommandResult.ok(_Payload(7))

    assert result.to_json() == '{"value": 7}'


def test_failed_carries_error() -> None:
    error = CommandError(CommandFailure.binary_missing, "fuzz not found")
    result = CommandResult[_Payload].failed(error)

    assert not result.is_ok
    assert result.error is error


def test_failed_serializes_error() -> None:
    error = CommandError(CommandFailure.binary_missing, "fuzz not found")
    result = CommandResult[_Payload].failed(error)

    assert result.to_json() == '{"ok": false, "error": "fuzz not found"}'


def test_unwrap_on_failure_raises() -> None:
    result = CommandResult[_Payload].failed(
        CommandError(CommandFailure.spec_not_found, "Spec file not found: x.tex")
    )

    with pytest.raises(ValueError, match="unwrap"):
        result.unwrap()


def test_construction_requires_exactly_one_of_payload_or_error() -> None:
    error = CommandError(CommandFailure.report_missing, "No report found for x")

    with pytest.raises(ValueError, match="exactly one"):
        CommandResult(None, None)
    with pytest.raises(ValueError, match="exactly one"):
        CommandResult(_Payload(1), error)


def test_command_error_dict_is_the_mcp_wire_shape() -> None:
    error = CommandError(
        CommandFailure.binary_missing,
        "fuzz not found",
        hint="Set $FUZZ or add fuzz to PATH.",
    )

    assert error.to_dict() == {"ok": False, "error": "fuzz not found"}


def test_command_failure_values_are_stable() -> None:
    assert CommandFailure.binary_missing == "binary_missing"
    assert CommandFailure.spec_not_found == "spec_not_found"
    assert CommandFailure.report_missing == "report_missing"
    assert CommandFailure.invalid_report == "invalid_report"
