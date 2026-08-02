"""Result envelope shared by every command."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol, Self, final


class JsonObject(Protocol):
    """A value that serializes to a JSON object."""

    # dict[str, Any] justified (PY-TS-14): JSON wire boundary — the values are
    # heterogeneous by definition, and every existing *.to_dict already returns
    # this shape (see types.py).
    def to_dict(self) -> dict[str, Any]: ...


class CommandFailure(StrEnum):
    """The expected, user-facing failure modes a command can return."""

    binary_missing = "binary_missing"
    spec_not_found = "spec_not_found"
    report_missing = "report_missing"
    invalid_report = "invalid_report"  # authored partition/audit JSON
    spec_unreadable = "spec_unreadable"  # parse/read failed after the file exists
    manifest_invalid = "manifest_invalid"  # manifest.toml malformed
    display_failed = "display_failed"  # lux surface unreachable
    not_a_repository = "not_a_repository"  # enable/disable outside a git repo


@final
@dataclass(frozen=True, slots=True)
class CommandError:
    """A structured failure. Each surface renders it its own way."""

    kind: CommandFailure
    message: str  # MCP-facing short text — matches current server.py strings
    hint: str = ""  # CLI-facing remediation suffix (e.g. "Set $FUZZ ...")

    def to_dict(self) -> dict[str, Any]:  # PY-TS-14 OK: JSON wire boundary
        return {"ok": False, "error": self.message}


@final
class CommandResult[PayloadT: JsonObject]:
    """Success carries a typed payload; failure carries a CommandError."""

    _payload: PayloadT | None  # None marks a failure; error carries the reason
    _error: CommandError | None  # None marks success; payload carries the value
    __slots__ = ("_error", "_payload")

    def __new__(cls, payload: PayloadT | None, error: CommandError | None) -> Self:
        if (payload is None) == (error is None):
            msg = "a command result carries exactly one of payload or error"
            raise ValueError(msg)
        self = super().__new__(cls)
        self._payload = payload
        self._error = error
        return self

    @classmethod
    def ok[P: JsonObject](cls, payload: P) -> CommandResult[P]:
        """Return a successful result carrying ``payload``."""
        return CommandResult(payload, None)

    @classmethod
    def failed(cls, error: CommandError) -> CommandResult[PayloadT]:
        """Return a failed result carrying ``error``."""
        return CommandResult(None, error)

    @property
    def is_ok(self) -> bool:
        return self._error is None

    @property
    def error(self) -> CommandError | None:  # PY-TS-14 OK: None documents success
        return self._error

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
