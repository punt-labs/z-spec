"""Result envelope shared by every command."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol, Self, final


class JsonObject(Protocol):
    """A value that serializes to a JSON object."""

    # dict[str, Any] justified (PY-TS-14): JSON wire boundary — the values are
    # heterogeneous by definition, and every to_dict returns this shape.
    def to_dict(self) -> dict[str, Any]:
        """Return this value as a JSON object."""
        ...


class _CheckReport(JsonObject, Protocol):
    """A report that carries the verdict of an executed check."""

    @property
    def ok(self) -> bool:
        """Return whether the check passed."""
        ...


class CommandFailure(StrEnum):
    """The expected, user-facing failure modes a command can return."""

    binary_missing = "binary_missing"
    check_failed = "check_failed"
    spec_not_found = "spec_not_found"
    report_missing = "report_missing"
    invalid_report = "invalid_report"  # authored partition/audit JSON
    spec_unreadable = "spec_unreadable"  # parse/read failed after the file exists
    manifest_invalid = "manifest_invalid"  # manifest.toml malformed
    display_failed = "display_failed"  # lux surface unreachable
    not_a_repository = "not_a_repository"  # enable/disable outside a git repo
    not_enabled = "not_enabled"  # no .punt-labs/z-spec/enabled marker here
    enablement_failed = "enablement_failed"  # the repo would not take the write


@final
@dataclass(frozen=True, slots=True)
class CommandError:
    """A structured failure. Each surface renders it its own way."""

    kind: CommandFailure
    message: str  # MCP-facing short text
    hint: str = ""  # remediation suffix (e.g. "Set $FUZZ ...")

    def to_dict(self) -> dict[str, Any]:  # PY-TS-14 OK: JSON wire boundary
        """Return the wire form of this error, with its hint when there is one."""
        # A declining gate puts the actionable half of its answer in the hint
        # ("commit the marker so the repo stays on"); without it an MCP caller
        # gets a refusal and no remedy.
        failure: dict[str, Any] = {"ok": False, "error": self.message}
        if self.hint:
            failure["hint"] = self.hint
        return failure


@final
class CommandResult[PayloadT: JsonObject]:
    """Carry a typed report or a command error when no report is available."""

    _payload: PayloadT | None
    _error: CommandError | None
    _failure: CommandFailure | None
    __slots__ = ("_error", "_failure", "_payload")

    def __new__(
        cls,
        payload: PayloadT | None,
        error: CommandError | None,
        *,
        failure: CommandFailure | None = None,
    ) -> Self:
        """Hold exactly one of ``payload`` and ``error``, with its failure kind.

        Raises:
            ValueError: Both or neither of ``payload`` and ``error`` are given.
        """
        if (payload is None) == (error is None):
            msg = "a command result carries exactly one of payload or error"
            raise ValueError(msg)
        self = super().__new__(cls)
        self._payload = payload
        self._error = error
        self._failure = error.kind if error is not None else failure
        return self

    @classmethod
    def ok[P: JsonObject](cls, payload: P) -> CommandResult[P]:
        """Return a successful result carrying ``payload``."""
        return CommandResult(payload, None)

    @classmethod
    def completed[P: JsonObject](
        cls, payload: P, *, failure: CommandFailure | None
    ) -> CommandResult[P]:
        """Return a report with its domain outcome, without changing its wire form."""
        return CommandResult(payload, None, failure=failure)

    @classmethod
    def checked[P: _CheckReport](cls, report: P) -> CommandResult[P]:
        """Return a check report with its verdict as diagnostic metadata."""
        failure = None if report.ok else CommandFailure.check_failed
        return CommandResult.completed(report, failure=failure)

    @classmethod
    def failed(cls, error: CommandError) -> CommandResult[PayloadT]:
        """Return a failed result carrying ``error``."""
        return CommandResult(None, error)

    @property
    def is_ok(self) -> bool:
        """Whether this result carries a payload."""
        return self._error is None

    @property
    def error(self) -> CommandError | None:  # PY-TS-14 OK: None documents success
        """Return the command error, or None if a report is available."""
        return self._error

    @property
    def failure(self) -> CommandFailure | None:
        """Return the failure kind from the command error or the domain verdict."""
        return self._failure

    def unwrap(self) -> PayloadT:
        """Return the payload, or raise if this result is a failure."""
        if self._payload is None:
            msg = "unwrap() on a failed command result"
            raise ValueError(msg)  # programmer error, not a user failure (PY-EH-8)
        return self._payload

    def to_json(self) -> str:
        """Serialize the payload or error to a JSON string."""
        if self._payload is not None:
            return json.dumps(self._payload.to_dict())
        error = self._error
        if error is None:  # unreachable by construction; keeps type checkers honest
            msg = "result has neither payload nor error"
            raise ValueError(msg)
        return json.dumps(error.to_dict())
